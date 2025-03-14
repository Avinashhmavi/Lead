import streamlit as st
import requests
from groq import Groq
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
from typing import List, Optional
import csv
import io
from datetime import datetime

# API Keys (replace with your own keys or use environment variables)
GROQ_API_KEY = "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"
FIRECRAWL_API_KEY = "fc-b07c21a470664f60b606b6538e252284"

class QuoraUserInteractionSchema(BaseModel):
    username: str = Field(description="The username of the user who posted the question or answer", default="")
    bio: str = Field(description="The bio or description of the user", default="")
    post_type: str = Field(description="The type of post, either 'question' or 'answer'", default="")
    timestamp: str = Field(description="When the question or answer was posted", default="")
    upvotes: int = Field(default=0, description="Number of upvotes received")
    links: List[str] = Field(default_factory=list, description="Any links included in the post")
    raw_text: Optional[str] = Field(default=None, description="Raw text content if structured data is unavailable")

class QuoraPageSchema(BaseModel):
    interactions: List[QuoraUserInteractionSchema] = Field(description="List of all user interactions (questions and answers) on the page")
    raw_content: Optional[str] = Field(default=None, description="Full raw content of the page if interactions are not found")

def search_for_urls(company_description: str, firecrawl_api_key: str, num_links: int) -> List[str]:
    """Search for Quora URLs based on the company description using Firecrawl API."""
    url = "https://api.firecrawl.dev/v1/search"
    headers = {
        "Authorization": f"Bearer {firecrawl_api_key}",
        "Content-Type": "application/json"
    }
    query = f"quora websites where people are looking for {company_description} services or information"
    payload = {
        "query": query,
        "limit": num_links,
        "lang": "en",
        "location": "India",
        "timeout": 60000,
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            results = data.get("data", [])
            return [result["url"] for result in results]
    return []

def extract_user_info_from_urls(urls: List[str], firecrawl_api_key: str) -> List[dict]:
    """Extract user information from Quora URLs using Firecrawl."""
    user_info_list = []
    firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
    
    try:
        for url in urls:
            st.write(f"Processing URL: {url}")
            response = firecrawl_app.extract(
                [url],
                {
                    'prompt': 'Extract all possible user information from Quora posts, including username, bio (if available), post type (question/answer), timestamp, upvotes, and any links. If structured interactions are unavailable, extract the full raw text content of the page and include it as "raw_text" or "raw_content". Focus on content related to management education or the specified query.',
                    'schema': QuoraPageSchema.model_json_schema(),
                }
            )
            
            st.write(f"Raw Firecrawl Response for {url}: {response}")
            if response.get('success') and response.get('status') == 'completed':
                data = response.get('data', {})
                interactions = data.get('interactions', [])
                raw_content = data.get('raw_content')
                
                if interactions:
                    user_info_list.append({
                        "website_url": url,
                        "user_info": interactions
                    })
                elif raw_content:
                    # Fallback: Use raw content as a lead indicator
                    user_info_list.append({
                        "website_url": url,
                        "user_info": [{
                            "username": "Unknown",
                            "bio": "",
                            "post_type": "question",
                            "timestamp": "",
                            "upvotes": 0,
                            "links": [],
                            "raw_text": raw_content[:1000]  # Limit to 1000 chars for brevity
                        }]
                    })
                    st.warning(f"No structured interactions found for {url}. Using raw content as fallback.")
                else:
                    st.warning(f"No interactions or raw content found for URL: {url}")
            else:
                st.error(f"Extraction failed for URL: {url}. Response: {response}")
    except Exception as e:
        st.error(f"Error extracting user info: {e}")
    
    return user_info_list

def format_user_info_to_flattened_json(user_info_list: List[dict]) -> List[dict]:
    """Convert extracted user info into a flattened JSON structure."""
    flattened_data = []
    
    for info in user_info_list:
        website_url = info["website_url"]
        user_info = info["user_info"]
        
        for interaction in user_info:
            flattened_interaction = {
                "Website URL": website_url,
                "Username": interaction.get("username", ""),
                "Bio": interaction.get("bio", ""),
                "Post Type": interaction.get("post_type", ""),
                "Timestamp": interaction.get("timestamp", ""),
                "Upvotes": interaction.get("upvotes", 0),
                "Links": ", ".join(interaction.get("links", [])),
                "Raw Text": interaction.get("raw_text", "")[:500]  # Limit to 500 chars for display
            }
            flattened_data.append(flattened_interaction)
    
    return flattened_data

def generate_csv(flattened_data):
    """Generate CSV data from flattened_data for download."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Define headers
    headers = ["Website URL", "Username", "Bio", "Post Type", "Timestamp", "Upvotes", "Links", "Raw Text"]
    writer.writerow(headers)
    
    # Write each data row
    for item in flattened_data:
        row = [
            item.get("Website URL", ""),
            item.get("Username", ""),
            item.get("Bio", ""),
            item.get("Post Type", ""),
            item.get("Timestamp", ""),
            str(item.get("Upvotes", 0)),
            item.get("Links", ""),
            item.get("Raw Text", "")[:1000]  # Limit to 1000 chars for CSV
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
    st.info("This Firecrawl-powered agent helps you generate leads from Quora by searching for relevant posts and extracting user information.")

    with st.sidebar:
        st.header("Configuration")
        firecrawl_api_key = FIRECRAWL_API_KEY
        groq_api_key = GROQ_API_KEY
        num_links = st.number_input("Number of links to search", min_value=1, max_value=10, value=3)
        
        if st.button("Reset"):
            st.session_state.clear()
            st.experimental_rerun()

    user_query = st.text_area(
        "Describe what kind of leads you're looking for:",
        placeholder="e.g., Looking for users who need automated video editing software with AI capabilities",
        help="Be specific about the product/service and target audience. The AI will convert this into a focused search query."
    )

    if st.button("Generate Leads"):
        if not all([firecrawl_api_key, groq_api_key, user_query]):
            st.error("Please fill in all the API keys and describe what leads you're looking for.")
        else:
            with st.spinner("Processing your query..."):
                company_description = transform_prompt(user_query, groq_api_key)
                st.write("🎯 Searching for:", company_description)
            
            with st.spinner("Searching for relevant URLs..."):
                urls = search_for_urls(company_description, firecrawl_api_key, num_links)
            
            if urls:
                st.subheader("Quora Links Used:")
                for url in urls:
                    st.write(url)
                
                with st.spinner("Extracting user info from URLs..."):
                    user_info_list = extract_user_info_from_urls(urls, firecrawl_api_key)
                
                with st.spinner("Formatting user info..."):
                    flattened_data = format_user_info_to_flattened_json(user_info_list)
                
                if flattened_data:
                    # Preview the first few rows
                    st.subheader("Preview of Extracted Data (First 5 rows)")
                    st.dataframe(flattened_data[:5])
                    
                    # Generate CSV with timestamp for uniqueness
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
                    st.error("No valid user data found to export. Check the Firecrawl responses above for details.")
            else:
                st.warning("No relevant URLs found.")

if __name__ == "__main__":
    main()
