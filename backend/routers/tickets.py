from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.models import Ticket, User, RoleEnum
from schemas.ticket import TicketCreate, TicketResponse, TicketStatusUpdate
from services.ticket_service import create_ticket_from_ai


router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


class AssignTicketRequest(BaseModel):
    assignee_id: str | None = None


@router.get("/", response_model=list[TicketResponse])
def get_tickets(db: Session = Depends(get_db)):
    return db.query(Ticket).order_by(Ticket.created_at.desc()).all()


@router.post("/", response_model=TicketResponse)
def create_ticket(ticket_in: TicketCreate, db: Session = Depends(get_db)):
    result = create_ticket_from_ai(
        db,
        issue_description=ticket_in.description,
        subject=ticket_in.subject,
        impact=ticket_in.impact,
        urgency=ticket_in.urgency,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return db.query(Ticket).filter(Ticket.ticket_number == result["ticket_number"]).one()


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: UUID, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(ticket_id: UUID, payload: TicketStatusUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = payload.status
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch("/{ticket_id}/assign")
def assign_ticket(ticket_id: UUID, payload: AssignTicketRequest, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    support_user = db.query(User).filter(User.role == RoleEnum.SUPPORT).first()
    if support_user is None:
        raise HTTPException(status_code=409, detail="No demo support user is configured")
    ticket.assignee_id = support_user.id
    if ticket.status == "OPEN":
        ticket.status = "IN_PROGRESS"
    db.commit()
    return {"status": "success", "message": "Ticket assigned to SOC", "new_status": ticket.status}
