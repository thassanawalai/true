from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from core.dependencies import get_db
from core.demo_auth import current_user, internal, visible_ticket
from models.models import Ticket, User, RoleEnum, TicketCategory, TicketComment
from schemas.ticket import TicketResponse, TicketStatusUpdate, TicketDetailResponse
from services.incident_assessment import POLICY, priority_components, priority_for
from services.ticket_service import create_ticket_from_ai
from routers.customer_data import authorized_company

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])
class TicketInput(BaseModel):
    subject: str = Field(max_length=200)
    description: str = Field(max_length=5000)
class AssignTicketRequest(BaseModel):
    assignee_id: UUID | None = None

@router.get("/", response_model=list[TicketResponse])
def get_tickets(company_id: UUID | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = db.query(Ticket)
    if company_id is not None or not internal(user):
        cid = authorized_company(db, user, company_id)
        query = query.filter(Ticket.company_id == cid)
    return query.order_by(Ticket.created_at.desc()).all()

@router.post("/", response_model=TicketResponse)
def create_ticket(ticket_in: TicketInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    result = create_ticket_from_ai(db, issue_description=ticket_in.description, subject=ticket_in.subject,
                                   company_id=user.company_id, requester_id=user.id)
    if not result["success"]:
        raise HTTPException(500, "Unable to create ticket")
    return db.query(Ticket).filter(Ticket.ticket_number == result["ticket_number"]).one()

@router.get("/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket(ticket_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ticket = visible_ticket(db, ticket_id, user)
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket.id)
    if not internal(user):
        comments = comments.filter(TicketComment.is_internal.is_(False))
    category = db.get(TicketCategory, ticket.category_id)
    calculation = None
    if (ticket.assessment and ticket.assessment.priority_policy == POLICY
            and priority_for(ticket.impact, ticket.urgency) == ticket.priority):
        impact_priority, urgency_priority = priority_components(ticket.impact, ticket.urgency)
        calculation = {'impact_priority': impact_priority, 'urgency_priority': urgency_priority}
    return {
        **TicketResponse.model_validate(ticket).model_dump(),
        'priority_calculation': calculation,
        'company_name': ticket.company.name if ticket.company else None,
        'requester_id': ticket.requester_id,
        'requester_name': ticket.requester.full_name if ticket.requester else None,
        'assignee_name': ticket.assignee.full_name if ticket.assignee else None,
        'category_name': category.name if category else None,
        'updated_at': ticket.updated_at,
        'comments': [{'id': c.id, 'sender_name': c.sender.full_name if c.sender else None,
                      'message': c.message, 'is_internal': c.is_internal, 'created_at': c.created_at}
                     for c in comments.order_by(TicketComment.created_at, TicketComment.id).all()],
    }

@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(ticket_id: UUID, payload: TicketStatusUpdate, db: Session = Depends(get_db),
                         user: User = Depends(current_user)):
    if not internal(user):
        raise HTTPException(403, "Support role required")
    ticket = visible_ticket(db, ticket_id, user)
    if payload.status not in {"NEW", "IN_PROGRESS", "PENDING", "RESOLVED"}:
        raise HTTPException(422, "Unsupported status")
    ticket.status = payload.status
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket

@router.patch("/{ticket_id}/assign")
def assign_ticket(ticket_id: UUID, payload: AssignTicketRequest, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    if not internal(user):
        raise HTTPException(403, "Support role required")
    ticket = visible_ticket(db, ticket_id, user)
    assignee = db.query(User).filter(User.id == payload.assignee_id).first() if payload.assignee_id else None
    if assignee and not internal(assignee):
        raise HTTPException(422, "Assignee must be support or admin")
    if payload.assignee_id and not assignee:
        raise HTTPException(404, "Assignee not found")
    ticket.assignee_id = assignee.id if assignee else None
    if assignee and ticket.status == "NEW":
        ticket.status = "IN_PROGRESS"
    db.commit()
    return {"status": "success", "new_status": ticket.status}
