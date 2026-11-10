"""Explicit demo-only user picker; not suitable for internet-facing production."""
import hmac
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from core.dependencies import get_db
from core.demo_auth import issue_token, current_user, internal, password_required, demo_passwords
from models.models import User, Company, RoleEnum
from core.rate_limits import FixedWindow

router = APIRouter(prefix="/api/demo-auth", tags=["Demo Login"])

_login_attempts = FixedWindow(60)


class LoginRequest(BaseModel):
    user_id: UUID
    password: str = Field(default="", max_length=256)

def public_user(user, company):
    return {"id": str(user.id), "name": user.full_name, "role": user.role.value,
            "company_id": str(user.company_id), "company": company.name if company else ""}

@router.get("/users")
def demo_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.email).all()
    companies = {c.id: c for c in db.query(Company).all()}
    required = password_required()
    credentials = demo_passwords() if required else {}
    return [dict(public_user(u, companies.get(u.company_id)), password_required=required) for u in users
            if u.email.endswith("@example.test") and (not required or u.email in credentials)]

@router.post("/login")
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    required = password_required()
    if required:
        client = http_request.client.host if http_request.client else 'unknown'
        if not _login_attempts.take(('global', 120), (('ip', client), 12), (('account', request.user_id), 6)):
            raise HTTPException(429, 'Too many login attempts', headers={'Retry-After': '60'})
    user = db.query(User).filter(User.id == request.user_id, User.email.endswith("@example.test")).first()
    if required:
        expected = demo_passwords().get(user.email) if user else None
        matches = hmac.compare_digest(request.password.encode(), (expected or 'invalid-login-placeholder').encode())
        if not expected or not matches:
            raise HTTPException(401, 'Invalid demo credentials')
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
