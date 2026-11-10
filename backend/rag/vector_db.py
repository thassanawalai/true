from functools import lru_cache


@lru_cache(maxsize=2)
def store(local_only=False):
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"local_files_only": local_only},
    )
    return Chroma(
        collection_name="soc_knowledge_base",
        embedding_function=embeddings,
        persist_directory="./chroma_data",
    )


def save_chunks_to_db(chunks: list, source_url: str, user_company: str = "public"):
    """Embed and save text chunks into the vector database with metadata."""
    from langchain_core.documents import Document

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
    store().add_documents(docs)
    print(f"[Vector DB] Successfully saved {len(docs)} chunks from {source_url}.")

def search_knowledge(query: str, user_company: str = "public", k: int = 3):
    """Search for the most relevant documents based on the query and company."""
    results = store().similarity_search(
        query=query, 
        k=k,
        filter={"user_company": user_company}
    )
    return results


def search_demo_playbooks(query: str, company_id: str, k: int = 3):
    """Constrain Chroma's search before retrieval and validate scope again in the caller."""
    return store(local_only=True).similarity_search(
        query=query, k=k, filter={"user_company": {"$in": ["public", company_id]}},
    )
