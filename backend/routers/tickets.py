from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from core.dependencies import get_db, get_current_user
from models.models import Ticket, TicketSLA, SLAPolicy, User, PriorityEnum, ImpactEnum, UrgencyEnum, SLAStatusEnum
from schemas.ticket import TicketCreate, TicketResponse, TicketAssign, TicketStatusUpdate
from models.models import Ticket, TicketSLA, SLAPolicy, User, PriorityEnum, ImpactEnum, UrgencyEnum, SLAStatusEnum, Company, TicketCategory

import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.models import (
    Company, TicketCategory, User, RoleEnum, Ticket, 
    TicketSLA, SLAPolicy, ImpactEnum, UrgencyEnum, PriorityEnum
)
from core.dependencies import get_db

from pydantic import BaseModel
from datetime import datetime
class AssignTicketRequest(BaseModel):
    assignee_id: str

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])

# Logic to calculate Priority based on Impact and Urgency
def calculate_priority(impact: ImpactEnum, urgency: UrgencyEnum) -> PriorityEnum:
    if impact == ImpactEnum.EXTENSIVE or urgency == UrgencyEnum.CRITICAL:
        return PriorityEnum.P1
    elif impact == ImpactEnum.SIGNIFICANT or urgency == UrgencyEnum.HIGH:
        return PriorityEnum.P2
    elif impact == ImpactEnum.MODERATE or urgency == UrgencyEnum.MEDIUM:
        return PriorityEnum.P3
    return PriorityEnum.P4

@router.post("/", response_model=TicketResponse)
def create_ticket(
    ticket_in: TicketCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Calculate Priority based on Impact and Urgency
    priority = calculate_priority(ticket_in.impact, ticket_in.urgency)
    
    # 2. Find matching SLA Policy or Auto-Create for MVP
    sla = db.query(SLAPolicy).filter(SLAPolicy.priority == priority).first()
    if not sla:
        sla = SLAPolicy(
            name=f"Default SLA for {priority.name}",
            priority=priority,
            time_to_own_minutes=60,      
            time_to_resolve_minutes=240 
        )
        db.add(sla)
        db.commit()
        db.refresh(sla)
        
    # 3. Bypass Dummy UUIDs: Fetch the first available company and category from DB
    default_company = db.query(Company).first()
    default_category = db.query(TicketCategory).first()

    # 4. Create Ticket
    ticket_num = f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    new_ticket = Ticket(
        ticket_number=ticket_num,
        company_id=default_company.id if default_company else ticket_in.company_id,
        requester_id=current_user.id, 
        category_id=default_category.id if default_category else ticket_in.category_id,
        subject=ticket_in.subject,
        description=ticket_in.description,
        impact=ticket_in.impact,
        urgency=ticket_in.urgency,
        priority=priority,
        sla_policy_id=sla.id,
        status="NEW"
    )
    db.add(new_ticket)
    db.flush() 

    # 5. Create SLA Tracking 
    now = datetime.utcnow()
    sla_tracking = TicketSLA(
        ticket_id=new_ticket.id,
        sla_policy_id=sla.id,
        ownership_due_at=now + timedelta(minutes=sla.time_to_own_minutes),
        resolution_due_at=now + timedelta(minutes=sla.time_to_resolve_minutes)
    )
    db.add(sla_tracking)
    db.commit()
    db.refresh(new_ticket)
    
    return new_ticket
    
@router.get("/", response_model=list[TicketResponse])
def get_tickets(db: Session = Depends(get_db)):
    return db.query(Ticket).order_by(Ticket.created_at.desc()).all()

@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@router.patch("/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
    ticket_id: uuid.UUID, 
    payload: TicketAssign, 
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.assignee_id = payload.assignee_id
    if ticket.status in ["NEW", "OPEN"]:
        ticket.status = "IN_PROGRESS"
    
    if not ticket.owned_at:
        ticket.owned_at = datetime.utcnow()
        
        if ticket.sla_tracking:
            ticket.sla_tracking.owned_at = ticket.owned_at
            if ticket.owned_at <= ticket.sla_tracking.ownership_due_at:
                ticket.sla_tracking.ownership_status = SLAStatusEnum.MET
            else:
                ticket.sla_tracking.ownership_status = SLAStatusEnum.MISSED

    db.commit()
    db.refresh(ticket)
    return ticket

@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: uuid.UUID, 
    payload: TicketStatusUpdate, 
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = payload.status
    
    if payload.status in ["RESOLVED", "CLOSED"] and not ticket.resolved_at:
        ticket.resolved_at = datetime.utcnow()
        
        if ticket.sla_tracking:
            ticket.sla_tracking.resolved_at = ticket.resolved_at
            if ticket.resolved_at <= ticket.sla_tracking.resolution_due_at:
                ticket.sla_tracking.resolution_status = SLAStatusEnum.MET
            else:
                ticket.sla_tracking.resolution_status = SLAStatusEnum.MISSED

    db.commit()
    db.refresh(ticket)
    return ticket

@router.post("/seed_mock_data", tags=["Development"])
def seed_mock_tickets(db: Session = Depends(get_db)):
    """
    Utility endpoint to quickly generate Master Data (Company, Users) 
    and realistic SOC tickets for MVP demonstration.
    """
    # 1. Create or fetch default Company
    company = db.query(Company).first()
    if not company:
        company = Company(name="True Digital Group (Demo)")
        db.add(company)
        db.commit()
        db.refresh(company)

    # 2. Create or fetch default Users (Customer & Support)
    customer = db.query(User).filter(User.role == RoleEnum.CUSTOMER).first()
    if not customer:
        customer = User(
            email="client@example.com", 
            full_name="Demo Customer", 
            role=RoleEnum.CUSTOMER, 
            company_id=company.id
        )
        db.add(customer)

    support = db.query(User).filter(User.role == RoleEnum.SUPPORT).first()
    if not support:
        support = User(
            email="analyst@soc.local", 
            full_name="SOC Analyst", 
            role=RoleEnum.SUPPORT, 
            company_id=company.id
        )
        db.add(support)

    # 3. Create or fetch Category
    category = db.query(TicketCategory).first()
    if not category:
        category = TicketCategory(name="Security Incident")
        db.add(category)
        
    db.commit()

    # 4. Define realistic SOC scenarios
    scenarios = [
        {
            "subject": "Phishing Email Reported: Password Reset Spoof", 
            "desc": "Multiple users reported receiving a suspicious password reset email claiming to be from IT. Domain looks slightly altered.", 
            "impact": ImpactEnum.MODERATE, "urgency": UrgencyEnum.MEDIUM, "status": "OPEN"
        },
        {
            "subject": "CrowdStrike Alert: Ransomware Behavior Blocked", 
            "desc": "Endpoint agent blocked a suspicious executable attempting to encrypt local files on HR-Laptop-05. Needs immediate isolation.", 
            "impact": ImpactEnum.SIGNIFICANT, "urgency": UrgencyEnum.CRITICAL, "status": "IN_PROGRESS"
        },
        {
            "subject": "Firewall CPU Utilization at 99%", 
            "desc": "Primary perimeter firewall is experiencing sustained 99% CPU load, causing severe network latency.", 
            "impact": ImpactEnum.EXTENSIVE, "urgency": UrgencyEnum.CRITICAL, "status": "NEW"
        }
    ]

    created_count = 0
    
    # 5. Inject tickets into the database using the new schema
    for s in scenarios:
        priority = calculate_priority(s["impact"], s["urgency"])
        sla = db.query(SLAPolicy).filter(SLAPolicy.priority == priority).first()
        
        if not sla:
            sla = SLAPolicy(
                name=f"Default SLA for {priority.name}", 
                priority=priority, 
                time_to_own_minutes=60, 
                time_to_resolve_minutes=240
            )
            db.add(sla)
            db.commit()
            db.refresh(sla)

        ticket_num = f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
        
        new_ticket = Ticket(
            ticket_number=ticket_num,
            company_id=company.id,
            requester_id=customer.id, # กำหนดให้ Customer เป็นคนเปิดตั๋ว
            assignee_id=support.id if s["status"] != "NEW" else None, # ถ้าสถานะไม่ใช่ NEW ให้ระบุชื่อ Support รับผิดชอบ
            category_id=category.id,
            subject=s["subject"],
            description=s["desc"],
            impact=s["impact"],
            urgency=s["urgency"],
            priority=priority,
            sla_policy_id=sla.id,
            status=s["status"]
        )
        db.add(new_ticket)
        db.flush()

        # Create SLA Tracking
        now = datetime.utcnow()
        sla_tracking = TicketSLA(
            ticket_id=new_ticket.id,
            sla_policy_id=sla.id,
            ownership_due_at=now + timedelta(minutes=sla.time_to_own_minutes),
            resolution_due_at=now + timedelta(minutes=sla.time_to_resolve_minutes)
        )
        db.add(sla_tracking)
        created_count += 1
        
    db.commit()
    
    return {
        "status": "success",
        "message": f"Successfully initialized master data and created {created_count} tickets."
    }

@router.patch("/{ticket_id}/assign", tags=["Tickets"])
def assign_ticket(
    ticket_id: str, 
    req: AssignTicketRequest, 
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    support_user = db.query(User).filter(User.role == RoleEnum.SUPPORT).first()
    
    if support_user:
        ticket.assignee_id = support_user.id
    else:
        ticket.assignee_id = req.assignee_id
        
    if ticket.status == "NEW":
        ticket.status = "IN_PROGRESS"
        
    if ticket.sla_tracking and not ticket.sla_tracking.owned_at:
        ticket.sla_tracking.owned_at = datetime.utcnow()
        
    db.commit()
    db.refresh(ticket)
    
    return {"status": "success", "message": "Ticket assigned to Support Team", "new_status": ticket.status}