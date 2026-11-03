"""Explicit demo-only user picker; not suitable for internet-facing production."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.dependencies import get_db
from core.demo_auth import issue_token, current_user, internal
from models.models import User, Company, RoleEnum

router = APIRouter(prefix="/api/demo-auth", tags=["Demo Login"])

class LoginRequest(BaseModel):
    user_id: str

def public_user(user, company):
    return {"id": str(user.id), "name": user.full_name, "role": user.role.value,
            "company_id": str(user.company_id), "company": company.name if company else ""}

@router.get("/users")
def demo_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.email).all()
    companies = {c.id: c for c in db.query(Company).all()}
    return [public_user(u, companies.get(u.company_id)) for u in users if u.email.endswith("@example.test")]

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == request.user_id, User.email.endswith("@example.test")).first()
    if not user:
        raise HTTPException(404, "Demo user not found")
    company = db.query(Company).filter(Company.id == user.company_id).first()
    return {"token": issue_token(user), "user": public_user(user, company)}

@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return public_user(user, db.query(Company).filter(Company.id == user.company_id).first())


@router.get("/companies")
def customer_companies(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not internal(user):
        raise HTTPException(403, "Support role required")
    companies = (db.query(Company).join(User).filter(User.role == RoleEnum.CUSTOMER,
                 Company.name != "Internal SOC (Demo)").distinct().order_by(Company.name).all())
    return [{"id": str(company.id), "name": company.name} for company in companies]
