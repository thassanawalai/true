import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Local imports
from routers import tickets
from core.dependencies import get_db
from core.llm_engine import generate_ai_response

app = FastAPI(title="SOC AI Support Assistant API")

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
    user_company: str

@app.get("/")
def read_root():
    return RedirectResponse(url="/chat")

@app.get("/chat", response_class=FileResponse)
def get_chat_ui():
    return "../frontend/templates/chat.html"
    
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    print(f"User message received: {request.message}")
    
    # The updated LLM engine now handles the two-step tool execution internally.
    # We simply pass the user message and the database session to it.
    ai_result = generate_ai_response(request.message, db)
    
    return ai_result