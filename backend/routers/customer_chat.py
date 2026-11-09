"""Tenant-authorized support Q&A with optional Gemini and rule-based fallback."""
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from sqlalchemy.orm import Session
from core.dependencies import get_db
from core.demo_auth import current_user
from models.models import User
from services.support_answers import answer_question

router = APIRouter(prefix='/api/customer-data', tags=['Customer Data Chat'])


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["knowledge", "analyze_log"] = "knowledge"
    details: bool = False
    message: str = Field(min_length=1, max_length=1000)
    company_id: UUID | None = None


@router.post('/ask')
def ask(request: AskRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return answer_question(request.message, db, user, request.company_id, action=request.action, details=request.details)


class ExperimentRequest(BaseModel):
    # Clients select a reviewed case, never supply a synthetic flag or evidence.
    model_config = ConfigDict(extra='forbid')
    case_id: str = Field(min_length=1, max_length=80)
    method: Literal['A', 'B']
    company_id: UUID | None = None


@router.post('/analyze-case')
def analyze_case(request: ExperimentRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    from fastapi import HTTPException
    from models.models import Company
    from routers.customer_data import authorized_company
    from services.incident_experiment import CASES, run_case
    cid = authorized_company(db, user, request.company_id)
    company = db.get(Company, cid)
    case = CASES.get(request.case_id)
    if not company or not case or case[0] != company.name:
        raise HTTPException(404, 'Synthetic case not available to this tenant')
    return run_case(request.case_id, request.method)
