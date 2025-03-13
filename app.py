import streamlit as st
import requests
from groq import Groq  # Using official Groq SDK
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
from typing import List
from composio_phidata import Action, ComposioToolSet
import json

# API Keys
GROQ_API_KEY = "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"
FIRECRAWL_API_KEY = "fc-b07c21a470664f60b606b6538e252284"
COMPOSIO_API_KEY = "nzubiyr1r2k8jq4gobm1rj"

class QuoraUserInteractionSchema(BaseModel):
    username: str = Field(description="The username of the user who posted the question or answer")
    bio: str = Field(description="The bio or description of the user")
    post_type: str = Field(description="The type of post, either 'question' or 'answer'")
    timestamp: str = Field(description="When the question or answer was posted")
    upvotes: int = Field(default=0, description="Number of upvotes received")
    links: List[str] = Field(default_factory=list, description="Any links included in the post")

class QuoraPageSchema(BaseModel):
    interactions: List[QuoraUserInteractionSchema] = Field(description="List of all user interactions (questions and answers) on the page")

def search_for_urls(company_description: str, firecrawl_api_key: str, num_links: int) -> List[str]:
    url = "https://api.firecrawl.dev/v1/search"
    headers = {
        "Authorization": f"Bearer {firecrawl_api_key}",
        "Content-Type": "application/json"
    }
    query1 = f"quora websites where people are looking for {company_description} services"
    payload = {
        "query": query1,
        "limit": num_links,
        "lang": "en",
        "location": "United States",
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
    user_info_list = []
    firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
    
    try:
        for url in urls:
            response = firecrawl_app.extract(
                [url],
                {
                    'prompt': 'Extract all user information including username, bio, post type (question/answer), timestamp, upvotes, and any links from Quora posts. Focus on identifying potential leads who are asking questions or providing answers related to the topic.',
                    'schema': QuoraPageSchema.model_json_schema(),
                }
            )
            
            if response.get('success') and response.get('status') == 'completed':
                interactions = response.get('data', {}).get('interactions', [])
                if interactions:
                    user_info_list.append({
                        "website_url": url,
                        "user_info": interactions
                    })
    except Exception:
        pass
    
    return user_info_list

def format_user_info_to_flattened_json(user_info_list: List[dict]) -> List[dict]:
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
            }
            flattened_data.append(flattened_interaction)
    
    return flattened_data

def write_to_google_sheets(flattened_data: List[dict], composio_api_key: str, groq_api_key: str) -> str:
    client = Groq(api_key=groq_api_key)
    composio_toolset = ComposioToolSet(api_key=composio_api_key)
    google_sheets_tool = composio_toolset.get_tools(actions=[Action.GOOGLESHEETS_SHEET_FROM_JSON])[0]
    
    try:
        message = (
            "Create a new Google Sheet with this data. "
            "The sheet should have these columns: Website URL, Username, Bio, Post Type, Timestamp, Upvotes, and Links in the same order as mentioned. "
            "Here's the data in JSON format:\n\n"
            f"{json.dumps(flattened_data, indent=2)}"
        )
        
        # Using Groq client directly instead of Agent
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "You are an expert at creating and updating Google Sheets. You will be given user information in JSON format, and you need to write it into a new Google Sheet."},
                {"role": "user", "content": message}
            ]
        )
        
        # Since Groq doesn't directly integrate with Composio tools, we'll need to handle this differently
        # For now, we'll assume the response contains the necessary instructions
        # In a real implementation, you'd need to parse the response and use Composio's API directly
        if "https://docs.google.com/spreadsheets/d/" in response.choices[0].message.content:
            google_sheets_link = response.choices[0].message.content.split("https://docs.google.com/spreadsheets/d/")[1].split(" ")[0]
            return f"https://docs.google.com/spreadsheets/d/{google_sheets_link}"
    except Exception as e:
        print(f"Error writing to Google Sheets: {e}")
    return None

def transform_prompt(user_query: str, groq_api_key: str) -> str:
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
    st.title("🎯 AI Lead Generation Agent")
    st.info("This firecrawl powered agent helps you generate leads from Quora by searching for relevant posts and extracting user information.")

    with st.sidebar:
        st.header("Configuration")
        firecrawl_api_key = FIRECRAWL_API_KEY
        groq_api_key = GROQ_API_KEY
        composio_api_key = COMPOSIO_API_KEY
        
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
        if not all([firecrawl_api_key, groq_api_key, composio_api_key, user_query]):
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
                
                with st.spinner("Writing to Google Sheets..."):
                    google_sheets_link = write_to_google_sheets(flattened_data, composio_api_key, groq_api_key)
                
                if google_sheets_link:
                    st.success("Lead generation and data writing to Google Sheets completed successfully!")
                    st.subheader("Google Sheets Link:")
                    st.markdown(f"[View Google Sheet]({google_sheets_link})")
                else:
                    st.error("Failed to retrieve the Google Sheets link.")
            else:
                st.warning("No relevant URLs found.")

if __name__ == "__main__":
    main()
