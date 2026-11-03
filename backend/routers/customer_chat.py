"""Tenant-authorized support Q&A with optional Gemini and rule-based fallback."""
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from core.dependencies import get_db
from core.demo_auth import current_user
from models.models import User
from services.support_answers import answer_question

router = APIRouter(prefix='/api/customer-data', tags=['Customer Data Chat'])


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    company_id: UUID | None = None


@router.post('/ask')
def ask(request: AskRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return answer_question(request.message, db, user, request.company_id)
