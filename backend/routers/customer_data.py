"""Tenant-scoped read-only customer telemetry endpoints (demo)."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.dependencies import get_db
from core.demo_auth import current_user, internal
from models.models import User, Company
from models.customer_data import CustomerAsset, LogCollector, CustomerLog

router = APIRouter(prefix="/api/customer-data", tags=["Customer Data"])

def authorized_company(db: Session, user: User, company_id: UUID | None):
    if internal(user):
        if company_id is None:
            raise HTTPException(422, "Internal users must select company_id")
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company or company.name == "Internal SOC (Demo)":
            raise HTTPException(404, "Customer company not found")
        return company.id
    if company_id is not None and company_id != user.company_id:
        raise HTTPException(403, "Access to another company is forbidden")
    return user.company_id

@router.get("/assets")
def assets(company_id: UUID | None = Query(default=None), db: Session = Depends(get_db),
           user: User = Depends(current_user)):
    cid = authorized_company(db, user, company_id)
    rows = db.query(CustomerAsset).filter(CustomerAsset.company_id == cid).order_by(CustomerAsset.ip_address).all()
    return [{"id": str(r.id), "ip_address": r.ip_address, "hostname": r.hostname, "asset_type": r.asset_type} for r in rows]

@router.get("/collectors")
def collectors(company_id: UUID | None = Query(default=None), db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    cid = authorized_company(db, user, company_id)
    rows = db.query(LogCollector).filter(LogCollector.company_id == cid).order_by(LogCollector.name).all()
    return [{"id": str(r.id), "name": r.name, "site": r.site} for r in rows]

@router.get("/logs")
def logs(company_id: UUID | None = Query(default=None), db: Session = Depends(get_db),
         user: User = Depends(current_user)):
    cid = authorized_company(db, user, company_id)
    # Foreign keys alone do not enforce company consistency. Exclude malformed
    # relationships before limiting results, including dangling references.
    rows = (db.query(CustomerLog)
            .join(CustomerAsset, CustomerLog.asset_id == CustomerAsset.id)
            .join(LogCollector, CustomerLog.collector_id == LogCollector.id)
            .filter(CustomerLog.company_id == cid,
                    CustomerAsset.company_id == cid, LogCollector.company_id == cid)
            .order_by(CustomerLog.occurred_at.desc()).limit(100).all())
    return [{"id": str(r.id), "asset_id": str(r.asset_id), "collector_id": str(r.collector_id),
             "event_type": r.event_type, "message": r.message, "occurred_at": r.occurred_at.isoformat()} for r in rows]
