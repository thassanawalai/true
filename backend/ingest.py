from rag.document_loader import get_mock_knowledge_base
from rag.vector_db import save_chunks_to_db

mock_data = get_mock_knowledge_base()

for item in mock_data:
    save_chunks_to_db(
        chunks=[item["content"]], 
        source_url=item["title"], 
        user_company=item["allowed_company"]
    )
print("Chroma DB complete")
