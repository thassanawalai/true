import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.models import (
    Company,
    ImpactEnum,
    SLAPolicy,
    Ticket,
    TicketAssessment,
    TicketCategory,
    UrgencyEnum,
    User,
)
from services.incident_assessment import assess, priority_for


def assess_ticket(subject, description, requester, company_name):
    description = description.strip() or "Security incident reported via AI assistant."
    subject = subject or description.splitlines()[0][:120] or "Security incident"
    return assess(subject, description, requester, company_name)


def create_ticket_from_ai(
    db: Session,
    issue_description: str,
    subject: str | None = None,
    impact: ImpactEnum | None = None,
    urgency: UrgencyEnum | None = None,
    company_id=None,
    requester_id=None,
    commit=True,
    assessed=None,
) -> dict:
    """Create a demo incident with the required foreign keys and SLA policy."""
    try:
        if company_id is None or requester_id is None:
            return {"success": False, "error": "Authenticated requester required"}
        company = db.query(Company).filter(Company.id == company_id).first()
        requester = db.query(User).filter(User.id == requester_id, User.company_id == company_id).first()
        if not company or not requester:
            return {"success": False, "error": "Invalid requester/company"}
        description = issue_description.strip() or "Security incident reported via AI assistant."
        analysis, metadata = assessed or assess_ticket(subject, description, requester, company.name)
        impact = impact or analysis.impact
        urgency = urgency or analysis.urgency
        priority = priority_for(impact, urgency)
        if impact != analysis.impact or urgency != analysis.urgency:
            metadata = {**metadata, 'source': 'manual_override'}

        category = db.query(TicketCategory).filter(TicketCategory.name == "Security Incident").first()
        if not category:
            category = TicketCategory(name="Security Incident")
            db.add(category)
            db.flush()

        sla = db.query(SLAPolicy).filter(SLAPolicy.priority == priority).first()
        if sla is None:
            sla = SLAPolicy(
                name=f"Demo SLA {priority.value}",
                priority=priority,
                time_to_own_minutes=60,
                time_to_resolve_minutes=240,
            )
            try:
                with db.begin_nested():
                    db.add(sla)
                    db.flush()
            except IntegrityError:
                sla = db.query(SLAPolicy).filter(SLAPolicy.priority == priority).one()

        subject = subject or description.splitlines()[0][:120] or "Security incident"
        ticket = Ticket(
            ticket_number=f"INC-{uuid.uuid4().hex[:8].upper()}",
            company_id=company.id,
            requester_id=requester.id,
            category_id=category.id,
            sla_policy_id=sla.id,
            subject=subject,
            description=description,
            impact=impact,
            urgency=urgency,
            priority=priority,
            status="NEW",
            created_at=datetime.utcnow(),
        )
        ticket.assessment = TicketAssessment(
            incident_type=analysis.incident_type,
            reason=analysis.reason,
            recommendation=analysis.recommendation,
            **metadata,
        )
        db.add(ticket)
        db.flush()
        if commit:
            db.commit()
        db.refresh(ticket)
        return {
            "success": True,
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "priority": ticket.priority.value,
        }
    except Exception:
        db.rollback()
        return {"success": False, "error": "Unable to create ticket"}
