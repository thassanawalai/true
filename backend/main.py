from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Literal
from uuid import UUID
from routers import tickets, demo_auth, customer_data, customer_chat, chat_rooms
from core.dependencies import get_db
from core.demo_auth import current_user
from core.database import Base, engine
from models import models
from models import customer_data as customer_data_models  # register demo tables
from core.deployment import hosted
from core.demo_gate import DemoAccessGate, settings as gate_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    gate_settings()
    if hosted():
        import os
        from sqlalchemy import inspect
        if len(os.getenv('DEMO_SESSION_SECRET', '')) < 32:
            raise RuntimeError('Set DEMO_SESSION_SECRET (at least 32 characters).')
        if not (STATIC_DIR / 'index.html').is_file():
            raise RuntimeError('Frontend build is missing from the deployment image.')
        # Validate only. Migrations are a separate, explicitly authorized operation.
        missing = set(Base.metadata.tables) - set(inspect(engine).get_table_names())
        if missing:
            raise RuntimeError('Database schema is incomplete; run the reviewed Alembic upgrade before deploying.')
    else:
        Base.metadata.create_all(bind=engine)
    import asyncio
    from services import temporary_chat
    async def expire_chats():
        while True:
            await asyncio.sleep(30)
            with temporary_chat.lock:
                temporary_chat.purge()
    cleanup = asyncio.create_task(expire_chats())
    try:
        yield
    finally:
        cleanup.cancel()
        try:
            await cleanup
        except asyncio.CancelledError:
            pass
        with temporary_chat.lock:
            temporary_chat.rooms.clear()

app = FastAPI(title="SOC AI Support Assistant API", lifespan=lifespan)
app.add_middleware(DemoAccessGate)
app.include_router(demo_auth.router)
app.include_router(tickets.router)
app.include_router(customer_data.router)
app.include_router(customer_chat.router)
app.include_router(chat_rooms.router)
# Vite proxies /api locally; explicit cross-origin access is disabled by default.

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    company_id: UUID | None = None

STATIC_DIR = Path(__file__).resolve().parent / "static"

@app.api_route('/healthz', methods=['GET', 'HEAD'], include_in_schema=False)
def health():
    from sqlalchemy import text
    from fastapi.responses import JSONResponse
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503)
    return {'status': 'ok'}

@app.get("/")
def read_root():
    if (STATIC_DIR / "index.html").is_file():
        return FileResponse(STATIC_DIR / "index.html")
    return {"status": "ok", "service": "SOC AI Support Assistant API"}

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db), user=Depends(current_user)):
    from fastapi import HTTPException
    try:
        from core.llm_engine import generate_ai_response
    except ImportError as exc:
        raise HTTPException(status_code=503, detail='AI provider not configured') from exc
    return generate_ai_response(request.message, db,
        history=[item.model_dump() for item in request.history[-20:]],
        user=user, company_id=request.company_id)


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        # Unknown API routes must remain API 404s, never the SPA shell.
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Keep missing assets and traversal attempts as 404s.
            if exc.status_code != 404 or Path(path).suffix or ".." in Path(path).parts:
                raise
            return await super().get_response("index.html", scope)


# Register last so all API routes retain precedence. Local Vite runs need no build.
if (STATIC_DIR / "index.html").is_file():
    app.mount("/", FrontendFiles(directory=STATIC_DIR, html=True), name="frontend")
