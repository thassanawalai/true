import uuid
from sqlalchemy.orm import Session
from models.models import Ticket

def create_ticket_from_ai(db: Session, issue_description: str) -> dict:
    """Creates a new incident ticket in the database from AI gathered information."""
    try:
        # Generate a unique incident number
        ticket_number = f"INC-{str(uuid.uuid4())[:8].upper()}"
        
        # Analyze priority based on critical keywords
        priority = "High" if "EDR" in issue_description.upper() or "หยุดทำงาน" in issue_description else "Medium"
        
        new_ticket = Ticket(
            ticket_number=ticket_number,
            subject="AI Automated Triage Incident",
            description=issue_description,
            status="Open",
            priority=priority,
            # Note: For multi-tenant, you will map user_id and company_id from the active session here
        )
        
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        
        return {
            "success": True, 
            "ticket_number": new_ticket.ticket_number,
            "priority": new_ticket.priority
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}