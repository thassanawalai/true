from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo only. Production should use Alembic migrations.
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
app.include_router(demo_auth.router)
app.include_router(tickets.router)
app.include_router(customer_data.router)
app.include_router(customer_chat.router)
app.include_router(chat_rooms.router)
# Vite proxies /api locally; explicit cross-origin access is disabled by default.

@app.exception_handler(RequestValidationError)
async def validation_error(_request, exc):
    # Validation errors can include raw passwords, reports, or chat prompts.
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': error['loc'], 'msg': error['msg'], 'type': error['type']} for error in exc.errors()
    ]})


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    company_id: UUID | None = None

@app.get("/")
def read_root():
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
