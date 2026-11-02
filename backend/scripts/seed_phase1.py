"""Idempotent demo fixtures; run with python scripts/seed_phase1.py from backend."""
from core.database import Base, engine, SessionLocal
from models.models import Company, User, RoleEnum
Base.metadata.create_all(bind=engine)
fixtures = [
    ("Company A (Demo)", "customer.a1@example.test", "Customer A1", RoleEnum.CUSTOMER),
    ("Company A (Demo)", "customer.a2@example.test", "Customer A2", RoleEnum.CUSTOMER),
    ("Company B (Demo)", "customer.b1@example.test", "Customer B1", RoleEnum.CUSTOMER),
    ("Internal SOC (Demo)", "support@example.test", "SOC Support", RoleEnum.SUPPORT),
    ("Internal SOC (Demo)", "admin@example.test", "SOC Admin", RoleEnum.ADMIN),
]
with SessionLocal() as db:
    for company_name, email, name, role in fixtures:
        company = db.query(Company).filter_by(name=company_name).first()
        if not company:
            company = Company(name=company_name)
            db.add(company)
            db.flush()
        user = db.query(User).filter_by(email=email).first()
        if not user:
            db.add(User(email=email, full_name=name, role=role, company_id=company.id))
    db.commit()
print("Demo users seeded")
