import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from models.models import (
    Company,
    ImpactEnum,
    PriorityEnum,
    RoleEnum,
    SLAPolicy,
    Ticket,
    TicketCategory,
    UrgencyEnum,
    User,
)


DEMO_COMPANY = "True Digital Group (Demo)"


def _get_demo_records(db: Session):
    company = db.query(Company).filter(Company.name == DEMO_COMPANY).first()
    if company is None:
        company = Company(name=DEMO_COMPANY)
        db.add(company)
        db.flush()

    requester = db.query(User).filter(User.email == "demo.customer@example.test").first()
    if requester is None:
        requester = User(
            email="demo.customer@example.test",
            full_name="Demo Customer",
            role=RoleEnum.CUSTOMER,
            company_id=company.id,
        )
        db.add(requester)

    support = db.query(User).filter(User.email == "soc.analyst@example.test").first()
    if support is None:
        support = User(
            email="soc.analyst@example.test",
            full_name="Demo SOC Analyst",
            role=RoleEnum.SUPPORT,
            company_id=company.id,
        )
        db.add(support)

    category = db.query(TicketCategory).filter(TicketCategory.name == "Security Incident").first()
    if category is None:
        category = TicketCategory(name="Security Incident")
        db.add(category)

    db.flush()
    return company, requester, category


def create_ticket_from_ai(
    db: Session,
    issue_description: str,
    subject: str | None = None,
    impact: ImpactEnum | None = None,
    urgency: UrgencyEnum | None = None,
) -> dict:
    """Create a demo incident with the required foreign keys and SLA policy."""
    try:
        company, requester, category = _get_demo_records(db)
        description = issue_description.strip() or "Security incident reported via AI assistant."
        upper = description.upper()
        critical_terms = ("RANSOMWARE", "MALWARE", "BREACH", "EXFILTRATION", "EDR", "CRITICAL")
        high = any(term in upper for term in critical_terms)
        impact = impact or (ImpactEnum.SIGNIFICANT if high else ImpactEnum.MODERATE)
        urgency = urgency or (UrgencyEnum.HIGH if high else UrgencyEnum.MEDIUM)
        if impact == ImpactEnum.EXTENSIVE or urgency == UrgencyEnum.CRITICAL:
            priority = PriorityEnum.P1
        elif impact == ImpactEnum.SIGNIFICANT or urgency == UrgencyEnum.HIGH:
            priority = PriorityEnum.P2
        elif impact == ImpactEnum.MODERATE or urgency == UrgencyEnum.MEDIUM:
            priority = PriorityEnum.P3
        else:
            priority = PriorityEnum.P4

        sla = db.query(SLAPolicy).filter(SLAPolicy.priority == priority).first()
        if sla is None:
            sla = SLAPolicy(
                name=f"Demo SLA {priority.value}",
                priority=priority,
                time_to_own_minutes=60,
                time_to_resolve_minutes=240,
            )
            db.add(sla)
            db.flush()

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
            status="OPEN",
            created_at=datetime.utcnow(),
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return {
            "success": True,
            "ticket_number": ticket.ticket_number,
            "priority": ticket.priority.value,
        }
    except Exception as exc:
        db.rollback()
        return {"success": False, "error": str(exc)}
