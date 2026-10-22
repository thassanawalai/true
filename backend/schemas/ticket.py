from pydantic import BaseModel
from typing import Optional
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

class TicketResponse(BaseModel):
    id: UUID
    ticket_number: str
    subject: str
    status: str
    impact: ImpactEnum
    urgency: UrgencyEnum
    priority: PriorityEnum
    created_at: datetime
    
    class Config:
        from_attributes = True

# 2 คลาสนี้แหละที่ระบบมันหาไม่เจอตอนรัน!
class TicketAssign(BaseModel):
    assignee_id: UUID

class TicketStatusUpdate(BaseModel):
    status: str