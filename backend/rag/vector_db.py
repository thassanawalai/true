import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

# Load environment variables
load_dotenv()

# Initialize Local Embedding Model (Runs securely on your machine)
print("[System] Initializing local embedding model. This might take a moment on the first run to download the model...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize Chroma vector database
vector_store = Chroma(
    collection_name="soc_knowledge_base",
    embedding_function=embeddings,
    persist_directory="./chroma_data" 
)

def save_chunks_to_db(chunks: list, source_url: str, user_company: str = "public"):
    """Embed and save text chunks into the vector database with metadata."""
    docs = []
    
    for i, chunk in enumerate(chunks):
        doc = Document(
            page_content=chunk,
            metadata={
                "source": source_url, 
                "chunk_id": i,
                "user_company": user_company
            }
        )
        docs.append(doc)
    
    # Add documents to ChromaDB (computes embeddings automatically)
    vector_store.add_documents(docs)
    print(f"[Vector DB] Successfully saved {len(docs)} chunks from {source_url}.")

def search_knowledge(query: str, user_company: str = "public", k: int = 3):
    """Search for the most relevant documents based on the query and company."""
    results = vector_store.similarity_search(
        query=query, 
        k=k,
        filter={"user_company": user_company}
    )
    return results