## 📝 AI Lead Generation Agent

Welcome to the **AI Lead Generation Agent**, a powerful tool powered by Firecrawl to extract potential leads from Quora based on your specified interests. This Streamlit application searches for relevant Quora posts, extracts user information (or raw content as a fallback), and provides the data as a downloadable CSV file.

[Live Demo](https://lead-marketing.streamlit.app/)

## Overview

This application leverages Firecrawl for web scraping, Groq for query transformation, and Streamlit for an interactive user interface. It is designed to help businesses or individuals identify potential leads by analyzing Quora discussions related to a specific topic or institution (e.g., IFIM College). Instead of relying on proprietary services like Google Sheets, it exports data in an open CSV format for easy accessibility.

## Features

- **Query Transformation**: Converts your descriptive lead query into a concise 3-4 word focus using Groq AI (e.g., "IFIM College" → "Business Education").
- **Quora Search**: Uses Firecrawl to find relevant Quora URLs based on your query.
- **Data Extraction**: Attempts to extract user interactions (username, bio, post type, timestamp, upvotes, links) from Quora posts. Falls back to raw text content if structured data is unavailable.
- **CSV Export**: Generates a downloadable CSV file with the extracted data, including a timestamp for uniqueness.
- **Data Preview**: Displays a preview of the first 5 rows of extracted data in the app.
- **Debugging Support**: Provides raw Firecrawl responses and error messages to help diagnose issues.
- **Customizable Search**: Allows you to adjust the number of links to search (1-10) via the sidebar.
- **Reset Option**: Clears the session state and refreshes the app with a single click.

## Pre-Installation

Before running the application locally, ensure you have the following dependencies and API keys set up:

### Prerequisites
- **Python 3.7+**: Ensure Python is installed on your system.
- **pip**: Python package manager (usually included with Python).

### Dependencies
Install the required Python packages using pip:
```bash
pip install streamlit requests groq firecrawl pydantic
```

### API Keys
You need API keys for the following services:
- **Groq API Key**: For query transformation. Sign up at [Groq](https://groq.com/) to obtain your key.
- **Firecrawl API Key**: For web scraping Quora. Sign up at [Firecrawl](https://firecrawl.dev/) to get your key.

Replace the placeholder keys in the code:
- `GROQ_API_KEY = "your_groq_api_key_here"`
- `FIRECRAWL_API_KEY = "your_firecrawl_api_key_here"`

**Recommendation**: For security, consider using environment variables or a `.env` file instead of hardcoding keys. You can use the `python-dotenv` package to load them:
```bash
pip install python-dotenv
```
Then modify the code to load keys like this:
```python
from dotenv import load_dotenv
import os

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
```

Create a `.env` file in the project directory with:
```
GROQ_API_KEY=your_groq_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
```

## Usage

1. **Clone or Download the Repository**:
   Save the provided Python code in a file named `app.py`.

2. **Run the Application**:
   Open a terminal, navigate to the directory containing `app.py`, and run:
   ```bash
   streamlit run lead_gen.py
   ```
   This will launch the app in your default web browser at `http://localhost:8501`.

3. **Configure the App**:
   - Enter your Groq and Firecrawl API keys in the sidebar or set them via environment variables.
   - Adjust the number of links to search (default is 3) using the sidebar input.
   - Describe the leads you're looking for in the text area (e.g., "IFIM College" or "AI video editing software").

4. **Generate Leads**:
   - Click the "Generate Leads" button to start the process.
   - View the Quora links used, raw Firecrawl responses, and a preview of the extracted data.
   - Download the CSV file using the provided button.

5. **Reset the App**:
   - Click the "Reset" button in the sidebar to clear the session and start fresh.

## Troubleshooting
- **No Data Extracted**: If you see "No valid user data found to export," check the raw Firecrawl responses. Quora’s anti-scraping measures or dynamic content might be the cause. Try adjusting the query or increasing the `timeout` in `search_for_urls`.
- **API Errors**: Ensure your API keys are valid and have sufficient quotas.
- **Empty CSV**: If the fallback raw text is not extracted, the issue may be with Firecrawl’s scraping capabilities for Quora.

## Contributing
Feel free to fork this repository, submit issues, or send pull requests to improve the project. Suggestions for adding support for other platforms (e.g., Reddit, LinkedIn) or enhancing data extraction are welcome!

## License
This project is open-source and available under the [MIT License](LICENSE) .

## Live Demo
Check out the live version of the app here: [https://lead-marketing.streamlit.app/](https://lead-marketing.streamlit.app/)
