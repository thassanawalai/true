# Demo setup

## 1. Configure the Gemini key

From the repository root, run `Copy-Item backend/.env.example backend/.env`, then
set `GEMINI_API_KEY` in `backend/.env` to the key for the demo machine. Keep
`.env` local; it is ignored by Git.

## 2. Build and ingest the playbooks

Run these commands from the repository root in PowerShell:

```powershell
docker compose -f backend/docker-compose.yml up -d db
docker compose -f backend/docker-compose.yml build backend
docker compose -f backend/docker-compose.yml run --rm backend python scripts/ingest_playbooks.py
docker compose -f backend/docker-compose.yml up -d backend frontend
```

The ingest command reads PDF, TXT, and Markdown files directly under
`backend/data/playbooks`. It stores vectors in the persistent `chroma_data`
Docker volume. The first run downloads the local embedding model. Ingest each
playbook set once; running it again can add duplicate chunks.

## 3. Open the demo

- Chat UI: <http://localhost:5173>
- API status: <http://localhost:8000>
- API documentation: <http://localhost:8000/docs>

The PostgreSQL schema is created when the backend starts. The demo ticket tool
uses one hard-coded demo company and customer; login is not enabled.
