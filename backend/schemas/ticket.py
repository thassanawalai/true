from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from models.models import ImpactEnum, UrgencyEnum, PriorityEnum


class TicketCreate(BaseModel):
    subject: str
    description: str
    category_id: UUID
    impact: ImpactEnum
    urgency: UrgencyEnum
    company_id: UUID

class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    model: str | None
    incident_type: str
    reason: str
    recommendation: str
    fallback_reason: str | None
    priority_policy: str


class TicketResponse(BaseModel):
    id: UUID
    company_id: UUID
    description: str
    assignee_id: UUID | None = None
    ticket_number: str
    subject: str
    status: str
    impact: ImpactEnum
    urgency: UrgencyEnum
    priority: PriorityEnum
    created_at: datetime
    assessment: AssessmentResponse | None = None
    
    class Config:
        from_attributes = True

# 2 คลาสนี้แหละที่ระบบมันหาไม่เจอตอนรัน!
class TicketAssign(BaseModel):
    assignee_id: UUID

class TicketStatusUpdate(BaseModel):
    status: str