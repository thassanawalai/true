"""Deterministic tenant-safe telemetry Q&A for the demo; no external LLM required."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from core.dependencies import get_db
from core.demo_auth import current_user
from models.models import User
from models.customer_data import CustomerAsset, LogCollector, CustomerLog
from routers.customer_data import authorized_company

router = APIRouter(prefix="/api/customer-data", tags=["Customer Data Chat"])

class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    company_id: UUID | None = None

@router.post("/ask")
def ask(request: AskRequest, db: Session = Depends(get_db),
        user: User = Depends(current_user)):
    # Scope first, then retrieve. Never let question text override company selection.
    cid = authorized_company(db, user, request.company_id)
    assets = db.query(CustomerAsset).filter(CustomerAsset.company_id == cid).order_by(CustomerAsset.ip_address).all()
    collectors = db.query(LogCollector).filter(LogCollector.company_id == cid).order_by(LogCollector.name).all()
    logs = db.query(CustomerLog).filter(CustomerLog.company_id == cid).order_by(CustomerLog.occurred_at.desc()).limit(100).all()
    asset_names = {a.id: a.hostname for a in assets}
    q = request.message.casefold()
    if any(word in q for word in ("collector", "lc", "ตัวเก็บ", "คอลเลกเตอร์")):
        answer = ("Log collectors: " + "; ".join(f"{c.name} ({c.site})" for c in collectors)) if collectors else "No log collectors found."
        kind = "collectors"
    elif any(word in q for word in ("ip", "asset", "host", "server", "เครื่อง", "ไอพี", "อุปกรณ์")):
        answer = ("Assets: " + "; ".join(f"{a.hostname} [{a.ip_address}] ({a.asset_type})" for a in assets)) if assets else "No assets found."
        kind = "assets"
    else:
        answer = ("Recent security events: " + "; ".join(
            f"{log.event_type} on {asset_names.get(log.asset_id, 'unknown asset')}: {log.message}"
            for log in logs[:10])) if logs else "No security events found."
        kind = "logs"
    return {"answer": answer, "source": "tenant_scoped_mock_data",
            "mode": "rule_based_demo", "category": kind,
            "company_id": str(cid), "counts": {"assets": len(assets), "collectors": len(collectors), "logs": len(logs)}}
