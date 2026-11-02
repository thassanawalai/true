from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Literal
from routers import tickets, demo_auth, customer_data, customer_chat
from core.dependencies import get_db
from core.demo_auth import current_user
from core.database import Base, engine
from models import models
from models import customer_data as customer_data_models  # register demo tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo only. Production should use Alembic migrations.
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="SOC AI Support Assistant API", lifespan=lifespan)
app.include_router(demo_auth.router)
app.include_router(tickets.router)
app.include_router(customer_data.router)
app.include_router(customer_chat.router)
# Vite proxies /api locally; explicit cross-origin access is disabled by default.

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)

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
        user=user)
