import streamlit as st
import requests
from groq import Groq
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
import csv
import io
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

# API Keys
GROQ_API_KEY = "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"
FIRECRAWL_API_KEY = "fc-b07c21a470664f60b606b6538e252284"

# Thread-safe list to store user info
user_info_list = []
user_info_lock = threading.Lock()

class UserInteractionSchema(BaseModel):
    username: str = Field(description="The username of the user who posted the content", default="")
    bio: str = Field(description="The bio or description of the user", default="")
    post_type: str = Field(description="The type of post (e.g., question, answer, post, comment)", default="")
    timestamp: str = Field(description="When the content was posted", default="")
    upvotes: int = Field(default=0, description="Number of upvotes, likes, or reactions received")
    links: List[str] = Field(default_factory=list, description="Any links included in the post")
    raw_text: Optional[str] = Field(default=None, description="Raw text content if structured data is unavailable")

class PageSchema(BaseModel):
    interactions: List[UserInteractionSchema] = Field(description="List of all user interactions on the page")
    raw_content: Optional[str] = Field(default=None, description="Full raw content of the page if interactions are not found")

def search_for_urls(company_description: str, firecrawl_api_key: str, num_links: int, platforms: List[str]) -> dict:
    """Search for URLs across specified platforms based on the company description using Firecrawl API."""
    platform_urls = {}
    url = "https://api.firecrawl.dev/v1/search"
    headers = {
        "Authorization": f"Bearer {firecrawl_api_key}",
        "Content-Type": "application/json"
    }
    
    for platform in platforms:
        if platform == "Internet":
            query = f"{company_description} services or information site:*.edu OR site:*.org OR site:*.gov -inurl:(signup OR login)"
        else:
            query = f"{company_description} services or information site:{platform.lower()}.com"
        
        payload = {
            "query": query,
            "limit": num_links,
            "lang": "en",
            "location": "India" if "India" in company_description else "United States",
            "timeout": 60000,
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                results = data.get("data", [])
                platform_urls[platform] = [result["url"] for result in results]
        else:
            st.warning(f"Failed to search for URLs on {platform}. Status code: {response.status_code}")
    
    return platform_urls

def extract_single_url(url: str, platform: str, firecrawl_app: FirecrawlApp, prompt: str, unsupported_platforms: set, max_retries: int = 2) -> Tuple[str, str, Optional[dict]]:
    """Extract user info from a single URL with retries and JavaScript rendering."""
    if platform in unsupported_platforms:
        return url, platform, None
    
    for attempt in range(max_retries + 1):
        try:
            response = firecrawl_app.extract(
                [url],
                {
                    'prompt': prompt,
                    'schema': PageSchema.model_json_schema(),
                    'options': {'render_js': True, 'timeout': 10}  # Enable JavaScript rendering
                }
            )
            
            if response.get('success') and response.get('status') == 'completed':
                data = response.get('data', {})
                raw_content = data.get('raw_content')
                interactions = data.get('interactions', [])
                
                if raw_content or interactions:
                    result = {}
                    if interactions:
                        result = {
                            "platform": platform,
                            "website_url": url,
                            "user_info": interactions
                        }
                    elif raw_content:
                        result = {
                            "platform": platform,
                            "website_url": url,
                            "user_info": [{
                                "username": "Unknown",
                                "bio": "",
                                "post_type": "post",
                                "timestamp": "",
                                "upvotes": 0,
                                "links": [],
                                "raw_text": raw_content[:1000]
                            }]
                        }
                    return url, platform, result
                else:
                    return url, platform, None
            else:
                st.write(f"Attempt {attempt + 1} failed for {url} on {platform}: {response}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return url, platform, None
        except Exception as e:
            error_msg = str(e)
            if "This website is no longer supported" in error_msg:
                with user_info_lock:
                    unsupported_platforms.add(platform)
                return url, platform, None
            st.error(f"Error extracting from {url} on {platform} (Attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return url, platform, None
    
    return url, platform, None

def extract_user_info_from_urls(platform_urls: dict, firecrawl_api_key: str) -> List[dict]:
    """Extract user information from URLs across different platforms using Firecrawl with parallel processing."""
    global user_info_list
    user_info_list = []
    unsupported_platforms = set()
    firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
    
    platform_prompts = {
        "Quora": "Extract all possible user information from Quora posts, including username, bio, post type (question/answer), timestamp, upvotes, and any links. Focus on content related to management education or the specified query. Prioritize raw content if structured data is unavailable.",
        "Reddit": "Extract user information from Reddit posts, including username, post type (post/comment), timestamp, upvotes, and any links. Focus on discussions related to the specified query. Prioritize raw content if structured data is unavailable.",
        "LinkedIn": "Extract user information from LinkedIn posts or profiles, including username, bio, post type (post/comment), timestamp, reactions, and any links. Focus on professional content related to the specified query. Prioritize raw content if structured data is unavailable.",
        "Internet": "Extract user information from general web pages (e.g., forums, blogs, educational sites), including author name, content type (article/post), timestamp, and any links. Focus on content related to the specified query. Prioritize raw content if structured data is unavailable."
    }
    
    tasks = []
    for platform, urls in platform_urls.items():
        if not urls:
            continue
        prompt = platform_prompts.get(platform, "Extract all possible user information, including username, bio, post type, timestamp, upvotes/reactions, and any links. Prioritize raw content if structured data is unavailable.")
        for url in urls:
            tasks.append((url, platform, prompt))
    
    total_tasks = len(tasks)
    if total_tasks == 0:
        return []
    
    st.write(f"Processing {total_tasks} URLs in parallel...")
    progress_bar = st.progress(0)
    completed_tasks = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(extract_single_url, url, platform, firecrawl_app, prompt, unsupported_platforms): (url, platform) for url, platform, prompt in tasks}
        
        for future in as_completed(future_to_url):
            url, platform = future_to_url[future]
            result = future.result()
            
            completed_tasks += 1
            progress_bar.progress(completed_tasks / total_tasks)
            
            if result[2]:
                with user_info_lock:
                    user_info_list.append(result[2])
                st.write(f"Successfully extracted data from {url} on {platform}")
            elif platform in unsupported_platforms:
                st.warning(f"Skipping {url} on {platform} due to Firecrawl restrictions.")
            else:
                st.warning(f"No data extracted from {url} on {platform}")
    
    if unsupported_platforms:
        st.info(f"Platforms skipped due to Firecrawl restrictions: {', '.join(unsupported_platforms)}. Contact help@firecrawl.com for support.")
    
    return user_info_list

def format_user_info_to_flattened_json(user_info_list: List[dict]) -> List[dict]:
    """Convert extracted user info into a flattened JSON structure."""
    flattened_data = []
    
    for info in user_info_list:
        platform = info["platform"]
        website_url = info["website_url"]
        user_info = info["user_info"]
        
        for interaction in user_info:
            flattened_interaction = {
                "Platform": platform,
                "Website URL": website_url,
                "Username": interaction.get("username", ""),
                "Bio": interaction.get("bio", ""),
                "Post Type": interaction.get("post_type", ""),
                "Timestamp": interaction.get("timestamp", ""),
                "Upvotes": interaction.get("upvotes", 0),
                "Links": ", ".join(interaction.get("links", [])),
                "Raw Text": interaction.get("raw_text", "")[:500]
            }
            flattened_data.append(flattened_interaction)
    
    return flattened_data

def generate_csv(flattened_data):
    """Generate CSV data from flattened_data for download."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = ["Platform", "Website URL", "Username", "Bio", "Post Type", "Timestamp", "Upvotes", "Links", "Raw Text"]
    writer.writerow(headers)
    
    for item in flattened_data:
        row = [
            item.get("Platform", ""),
            item.get("Website URL", ""),
            item.get("Username", ""),
            item.get("Bio", ""),
            item.get("Post Type", ""),
            item.get("Timestamp", ""),
            str(item.get("Upvotes", 0)),
            item.get("Links", ""),
            item.get("Raw Text", "")[:1000]
        ]
        writer.writerow(row)
    
    return output.getvalue()

def transform_prompt(user_query: str, groq_api_key: str) -> str:
    """Transform user query into a concise company description using Groq."""
    client = Groq(api_key=groq_api_key)
    system_prompt = """You are an expert at transforming detailed user queries into concise company descriptions.
Your task is to extract the core business/product focus in 3-4 words.

Examples:
Input: "Generate leads looking for AI-powered customer support chatbots for e-commerce stores."
Output: "AI customer support chatbots for e commerce"

Input: "Find people interested in voice cloning technology for creating audiobooks and podcasts"
Output: "voice cloning technology"

Input: "Looking for users who need automated video editing software with AI capabilities"
Output: "AI video editing software"

Input: "Need to find businesses interested in implementing machine learning solutions for fraud detection"
Output: "ML fraud detection"

Always focus on the core product/service and keep it concise but clear."""
    
    response = client.chat.completions.create(
        model="mixtral-8x7b-32768",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transform this query into a concise 3-4 word company description: {user_query}"}
        ]
    )
    return response.choices[0].message.content

def main():
    """Main function to run the Streamlit app."""
    st.title("🎯 AI Lead Generation Agent")
    st.info("This Firecrawl-powered agent helps you generate leads from multiple platforms by searching for relevant posts and extracting user information.")

    with st.sidebar:
        st.header("Configuration")
        firecrawl_api_key = FIRECRAWL_API_KEY
        groq_api_key = GROQ_API_KEY
        num_links = st.number_input("Number of links per platform", min_value=1, max_value=10, value=3)
        platforms = st.multiselect(
            "Select platforms to search",
            options=["Quora", "Reddit", "LinkedIn", "Internet"],
            default=["Quora"]
        )
        
        if st.button("Reset"):
            st.session_state.clear()
            st.experimental_rerun()

    user_query = st.text_area(
        "Describe what kind of leads you're looking for:",
        placeholder="e.g., Looking for users who need automated video editing software with AI capabilities",
        help="Be specific about the product/service and target audience. The AI will convert this into a focused search query."
    )

    if st.button("Generate Leads"):
        if not all([firecrawl_api_key, groq_api_key, user_query, platforms]):
            st.error("Please fill in all the API keys, describe what leads you're looking for, and select at least one platform.")
        else:
            with st.spinner("Processing your query..."):
                company_description = transform_prompt(user_query, groq_api_key)
                st.write("🎯 Searching for:", company_description)
            
            with st.spinner("Searching for relevant URLs..."):
                platform_urls = search_for_urls(company_description, firecrawl_api_key, num_links, platforms)
            
            if platform_urls:
                for platform, urls in platform_urls.items():
                    if urls:
                        st.subheader(f"{platform} Links Used:")
                        for url in urls:
                            st.write(url)
                    else:
                        st.warning(f"No URLs found for {platform}.")
                
                with st.spinner("Extracting user info from URLs..."):
                    user_info_list = extract_user_info_from_urls(platform_urls, firecrawl_api_key)
                
                with st.spinner("Formatting user info..."):
                    flattened_data = format_user_info_to_flattened_json(user_info_list)
                
                if flattened_data:
                    st.subheader("Preview of Extracted Data (First 5 rows)")
                    st.dataframe(flattened_data[:5])
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_data = generate_csv(flattened_data)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"lead_generation_{timestamp}.csv",
                        mime="text/csv"
                    )
                    st.success("Lead generation completed successfully! Click the button above to download the CSV file.")
                else:
                    st.error("No valid user data found to export. Check the logs above for details. This may be due to Firecrawl restrictions or website protections.")
            else:
                st.warning("No relevant URLs found across selected platforms.")

if __name__ == "__main__":
    main()
