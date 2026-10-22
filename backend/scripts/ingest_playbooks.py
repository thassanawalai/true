import os
import sys
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Ensure backend directory is in the path to import rag module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rag.vector_db import save_chunks_to_db

# Define the directory where playbook files will be stored
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(BASE_DIR, "data", "playbooks")

def ingest_documents(company_name="True Digital Group (Demo)"):
    """Reads PDF and TXT files, splits them into chunks, and saves to ChromaDB."""
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print(f"[Info] Created directory at {DOCS_DIR}. Please place your playbook files there.")
        return

    files = [f for f in os.listdir(DOCS_DIR) if f.endswith(('.pdf', '.txt'))]
    if not files:
        print(f"[Warning] No supported files (.pdf, .txt) found in {DOCS_DIR}.")
        return

    # Initialize text splitter for optimal LLM context window size
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " ", ""]
    )

    for filename in files:
        file_path = os.path.join(DOCS_DIR, filename)
        print(f"[Process] Loading and chunking: {filename}...")
        
        try:
            if filename.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif filename.endswith(".txt"):
                loader = TextLoader(file_path, encoding="utf-8")
            
            docs = loader.load()
            chunks = text_splitter.split_documents(docs)
            
            # Extract raw text from LangChain Document objects
            chunk_texts = [chunk.page_content for chunk in chunks]
            
            # Save into ChromaDB using the existing function
            save_chunks_to_db(chunks=chunk_texts, source_url=filename, user_company=company_name)
            
        except Exception as e:
            print(f"[Error] Failed to process {filename}: {str(e)}")

if __name__ == "__main__":
    print("--- Starting Playbook Ingestion ---")
    ingest_documents()
    print("--- Ingestion Complete ---")