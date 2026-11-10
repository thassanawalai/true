"""Demo-only signed bearer sessions. Replace with real identity provider before production."""
import base64
import hashlib
import hmac
import json
import os
import time
from uuid import UUID
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from core.dependencies import get_db
from models.models import User, RoleEnum

def _secret():
    secret = os.getenv("DEMO_SESSION_SECRET", "")
    if len(secret) < 32 or secret == "replace-with-a-unique-random-secret-at-least-32-chars":
        raise HTTPException(503, "Set DEMO_SESSION_SECRET (at least 32 characters) for demo login")
    return secret.encode()

def password_required():
    return (os.getenv('DEMO_AUTH_MODE', '').lower() == 'password'
            or os.getenv('GEMINI_ENABLED', '').lower() == 'true')


def demo_passwords():
    try:
        values = json.loads(os.getenv('DEMO_LOGIN_PASSWORDS_JSON', '{}'))
    except ValueError:
        values = {}
    if not isinstance(values, dict) or any(
        not isinstance(password, str) or not 16 <= len(password) <= 256
        for password in values.values()
    ) or len(set(values.values())) != len(values):
        return {}
    return values


def issue_token(user):
    payload = json.dumps({"uid": str(user.id), "exp": int(time.time()) + 8 * 3600, "password": password_required()}, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + signature

def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Login required")
    try:
        body, signature = authorization[7:].split(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) <= time.time():
            raise ValueError("Expired")
        if password_required() and payload.get('password') is not True:
            raise ValueError('Password sign-in required')
        user = db.query(User).filter(User.id == UUID(payload["uid"])).first()
        if not user or (password_required() and user.email not in demo_passwords()):
            raise ValueError("Unknown user")
        return user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Invalid or expired demo session")

def internal(user):
    return user.role in (RoleEnum.SUPPORT, RoleEnum.ADMIN)

def visible_ticket(db, ticket_id, user):
    from models.models import Ticket
    q = db.query(Ticket).filter(Ticket.id == ticket_id)
    if not internal(user):
        q = q.filter(Ticket.company_id == user.company_id)
    ticket = q.first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return ticket
