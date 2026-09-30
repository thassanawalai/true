from sqlalchemy.orm import Session
from core.database import SessionLocal, engine
from models.models import Base, Customer, User, Category, Ticket, KnowledgeArticle
from passlib.context import CryptContext

# Password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def seed_data():
    db = SessionLocal()
    
    # Check if data already exists to prevent duplication
    if db.query(Customer).first():
        print("⚠️ Data already exists. Skipping seed.")
        db.close()
        return

    print("Seeding data...")

    # 1. Create Customers
    cust1 = Customer(company_name="Demeter ICT", contact_email="contact@demeterict.com", sla_plan="Premium")
    cust2 = Customer(company_name="ABC Corp", contact_email="contact@abccorp.com", sla_plan="Standard")
    db.add_all([cust1, cust2])
    db.commit()

    # 2. Create Users (Default password is '123456')
    admin = User(email="admin@soc.com", password_hash=get_password_hash("123456"), role="ADMIN")
    agent = User(email="agent@soc.com", password_hash=get_password_hash("123456"), role="SUPPORT_AGENT")
    client1 = User(email="client@demeterict.com", password_hash=get_password_hash("123456"), role="CUSTOMER", customer_id=cust1.id)
    db.add_all([admin, agent, client1])
    db.commit()

    # 3. Create Categories
    cat_net = Category(name="Network", description="VPN, Wi-Fi, LAN issues")
    cat_sec = Category(name="Security", description="Malware, Phishing, Access Control")
    db.add_all([cat_net, cat_sec])
    db.commit()

    # 4. Create Knowledge Articles
    kb1 = KnowledgeArticle(title="How to fix VPN Error 809", content="1. Check internet connection.\n2. Restart VPN client.", category_id=cat_net.id)
    kb2 = KnowledgeArticle(title="Ransomware Response", content="Isolate the host immediately and notify Tier 2.", category_id=cat_sec.id)
    db.add_all([kb1, kb2])
    db.commit()

    # 5. Create Mock Tickets
    t1 = Ticket(
        subject="CrowdStrike malware alert on Server 01",
        description="Detected Ransomware on SRV-PROD-01. Host isolated.",
        priority="1 - Critical",
        status="OPEN",
        customer_id=cust1.id,
        created_by=client1.id,
        category_id=cat_sec.id
    )
    t2 = Ticket(
        subject="Cannot connect to Corporate VPN",
        description="Getting Error 809 when trying to connect.",
        priority="3 - Normal",
        status="IN_PROGRESS",
        customer_id=cust1.id,
        created_by=client1.id,
        assigned_to=agent.id,
        category_id=cat_net.id
    )
    db.add_all([t1, t2])
    db.commit()

    print("✅ Mock data seeded successfully!")
    db.close()

if __name__ == "__main__":
    seed_data()