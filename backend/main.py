from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Literal

# Local imports
from routers import tickets
from core.dependencies import get_db
from core.llm_engine import generate_ai_response
from core.database import Base, engine
from models import models  # Register ORM tables before creating the demo schema.


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Authentication and migrations are intentionally omitted for this demo.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="SOC AI Support Assistant API", lifespan=lifespan)

# Register Ticket Routers
app.include_router(tickets.router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)

class ChatRequest(BaseModel):
    message: str
    history: list["ChatMessage"] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

@app.get("/")
def read_root():
    return {"status": "ok", "service": "SOC AI Support Assistant API"}

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    print(f"User message received: {request.message}")
    return generate_ai_response(
        request.message,
        db,
        history=[item.model_dump() for item in request.history[-20:]],
    )
