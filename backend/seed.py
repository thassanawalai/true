import os
import uuid
from datetime import datetime, timezone
from passlib.context import CryptContext
from core.database import SessionLocal
from models.models import Company, Team, SLAPolicy, TicketCategory, User, PriorityEnum

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def seed_data():
    db = SessionLocal()
    try:
        # เช็กว่ามีข้อมูลอยู่แล้วหรือยัง
        if db.query(Company).first():
            print("Seed data already exists. Skipping initialization.")
            return

        print("Generating seed data...")

        # 1. Create Company
        comp = Company(
            company_code="TDG",
            company_name="True Digital Group",
            industry="Cybersecurity",
            support_tier="Enterprise"
        )
        db.add(comp)
        db.commit()
        db.refresh(comp)

        # 2. Create SLA Policies (อัปเดตให้ตรงกับระบบ Time to Own/Resolve)
        sla_p1 = SLAPolicy(
            name="P1 - Critical",
            priority=PriorityEnum.P1,
            time_to_own_minutes=15,
            time_to_resolve_minutes=240
        )
        sla_p2 = SLAPolicy(
            name="P2 - High",
            priority=PriorityEnum.P2,
            time_to_own_minutes=30,
            time_to_resolve_minutes=480
        )
        db.add_all([sla_p1, sla_p2])
        db.commit()
        db.refresh(sla_p1)
        db.refresh(sla_p2)

        # 3. Create Teams
        team_siem = Team(
            team_code="SEC-SIEM",
            team_name="SIEM Operations",
            description="Cybersecurity and SIEM Alerts"
        )
        db.add(team_siem)
        db.commit()
        db.refresh(team_siem)

        # 4. Create Ticket Categories (ล็อกค่า Default Impact/Urgency/Priority ให้ตรง Enum)
        cat_sec = TicketCategory(
            category_code="SEC-INC-01",
            ticket_type="INCIDENT",
            main_category="Security",
            sub_category="SIEM Alert",
            default_impact="EXTENSIVE",
            default_urgency="CRITICAL",
            default_priority="P1"
        )
        db.add(cat_sec)
        db.commit()

        # 5. Create Admin User
        admin_user = User(
            company_id=comp.id,
            name="Admin Thasanawalai",
            email="admin@truedigital.com",
            password_hash=get_password_hash("Admin@1234"),
            role="ADMIN",
            job_title="System Administrator",
            availability_status="ONLINE"
        )
        db.add(admin_user)
        db.commit()

        print("✅ Seed data generated successfully!")

    except Exception as e:
        print(f"❌ Error generating seed data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()