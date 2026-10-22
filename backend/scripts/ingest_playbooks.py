import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

# Ensure the backend directory is in the path to import rag modules.
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))
from rag.vector_db import save_chunks_to_db

DOCS_DIR = BASE_DIR / "data" / "playbooks"
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def load_playbook(file_path: Path) -> list[Document]:
    """Load a PDF, plain text, or Markdown playbook."""
    if file_path.suffix.lower() == ".pdf":
        reader = PdfReader(str(file_path))
        return [
            Document(
                page_content=page.extract_text() or "",
                metadata={"source": file_path.name, "page": page_number},
            )
            for page_number, page in enumerate(reader.pages, start=1)
        ]

    text = file_path.read_text(encoding="utf-8-sig")
    return [Document(page_content=text, metadata={"source": file_path.name})]


def ingest_documents(company_name="True Digital Group (Demo)"):
    """Read playbooks, split them into chunks, and save them to ChromaDB."""
    if not DOCS_DIR.exists():
        DOCS_DIR.mkdir(parents=True)
        print(f"[Info] Created directory at {DOCS_DIR}. Please place your playbook files there.")
        return

    files = sorted(
        path for path in DOCS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        print(f"[Warning] No supported files (.pdf, .txt, .md) found in {DOCS_DIR}.")
        return

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    for file_path in files:
        print(f"[Process] Loading and chunking: {file_path.name}...")
        try:
            docs = load_playbook(file_path)
            chunks = text_splitter.split_documents(
                [doc for doc in docs if doc.page_content.strip()]
            )
            chunk_texts = [chunk.page_content for chunk in chunks]
            if not chunk_texts:
                print(f"[Warning] No extractable text found in {file_path.name}.")
                continue

            save_chunks_to_db(
                chunks=chunk_texts,
                source_url=file_path.name,
                user_company=company_name,
            )
        except Exception as exc:
            print(f"[Error] Failed to process {file_path.name}: {exc}")


if __name__ == "__main__":
    print("--- Starting Playbook Ingestion ---")
    ingest_documents()
    print("--- Ingestion Complete ---")
