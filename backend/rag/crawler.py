import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag.vector_db import save_chunks_to_db

# Whitelist of allowed domains to prevent unauthorized scraping
ALLOWED_DOMAINS = [
    "docs.python.org",
    "fastapi.tiangolo.com",
    # Add client knowledge base domains here
]

def is_allowed_url(url: str) -> bool:
    """Check if the URL belongs to an allowed domain."""
    try:
        domain = urlparse(url).netloc
        return domain in ALLOWED_DOMAINS
    except Exception:
        return False

def scrape_web_content(url: str):
    """Scrape text content from a given URL."""
    if not is_allowed_url(url):
        return {"status": "error", "message": f"Domain not allowed: {url}"}

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script, style, nav, footer, and header elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        # Extract plain text
        text = soup.get_text(separator=' ', strip=True)
        clean_text = ' '.join(text.split())

        return {
            "status": "success",
            "url": url,
            "content_length": len(clean_text),
            "content": clean_text
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to scrape data: {str(e)}"}

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    """Split text into overlapping chunks for embedding."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""] 
    )
    return text_splitter.split_text(text)

if __name__ == "__main__":
    test_url = "https://fastapi.tiangolo.com/"
    print(f"Starting crawler for URL: {test_url}")
    
    result = scrape_web_content(test_url)
    
    if result["status"] == "success":
        full_text = result["content"]
        print(f"Scraping successful. Total length: {result['content_length']} characters.")
        
        print("Starting text chunking process...")
        chunks = chunk_text(full_text)
        print(f"Chunking completed. Total chunks generated: {len(chunks)}")
        
        print("Saving chunks to Vector Database...")
        save_chunks_to_db(chunks, source_url=test_url, user_company="public")
        print("Crawler pipeline executed successfully.")
            
    else:
        print(f"Error: {result['message']}")