from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import SessionLocal
from models.models import User

# ฟังก์ชันเชื่อมต่อ Database
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Mock Auth: คืนค่า Admin User เสมอเพื่อใช้ทดสอบ Workflow
def get_current_user(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == "admin@truedigital.com").first()
    if not user:
        raise HTTPException(status_code=404, detail="Mock user not found. Did you run seed.py?")
    return user