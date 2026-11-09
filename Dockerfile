FROM node:24-bookworm-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements-demo.txt .
# Active JSON-KB demo needs no Torch, embeddings or vector database.
RUN pip install --no-cache-dir -r requirements-demo.txt

COPY backend/ .
COPY --from=frontend-build /frontend/dist ./static

EXPOSE 8080
ENV APP_ENV=production GEMINI_ENABLED=false PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
