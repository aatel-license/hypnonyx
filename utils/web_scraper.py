#!/usr/bin/env python3
"""
Simple web scraper to fetch and return text content from a URL.
 usage: python3 web_scraper.py <url>
"""
import sys
import json
import requests
from bs4 import BeautifulSoup
import traceback

def fetch_content(url: str) -> dict:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
            
        # Get text
        text = soup.get_text()
        
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return {
            "url": url,
            "title": soup.title.string if soup.title else "",
            "content": text[:8000], # Limit content to 8000 chars to fit in context
            "error": None
        }
        
    except Exception as e:
        return {
            "url": url,
            "title": "",
            "content": "",
            "error": str(e)
        }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No URL provided"}))
        sys.exit(1)
        
    url = sys.argv[1]
    result = fetch_content(url)
    print(json.dumps(result))
