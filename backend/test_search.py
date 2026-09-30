from rag.vector_db import search_knowledge

# ลองค้นหาเรื่องที่มีใน Mock Data (เช่น Log Loss)
query = "How to fix Log Loss issue?"

print(f"Search Query: '{query}'")
print("Searching the vector database...\n")
print("-" * 50)

# ใส่ user_company="ALL" เพื่อให้เข้าถึงเอกสาร KB-001 ได้
results = search_knowledge(query=query, user_company="ALL", k=2)

# Display results
if results:
    for i, doc in enumerate(results):
        print(f"Result {i+1}:")
        print(f"Content:\n{doc.page_content}\n")
        print(f"Metadata: {doc.metadata}")
        print("-" * 50)
else:
    print("No relevant information found.")