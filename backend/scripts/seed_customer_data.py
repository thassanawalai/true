"""Idempotent demo telemetry seed. Run from backend: PYTHONPATH=. python scripts/seed_customer_data.py"""
from core.database import Base, engine, SessionLocal
from models import models  # noqa: F401; register existing tables
from models.customer_data import CustomerAsset, LogCollector, CustomerLog

Base.metadata.create_all(bind=engine)
fixtures = {
    "Company A (Demo)": ("LC-A-01", "Bangkok", [
        ("192.0.2.10", "a-web-01", "WEB_SERVER", "SUSPICIOUS_LOGIN", "Multiple failed login attempts"),
        ("192.0.2.20", "a-db-01", "DATABASE", "ACCESS_DENIED", "Database login denied"),
    ]),
    "Company B (Demo)": ("LC-B-01", "Chiang Mai", [
        ("198.51.100.10", "b-web-01", "WEB_SERVER", "PORT_SCAN", "Unusual connection attempts"),
        ("198.51.100.20", "b-fw-01", "FIREWALL", "BLOCKED_TRAFFIC", "Firewall blocked suspicious traffic"),
    ]),
}
with SessionLocal() as db:
    for company_name, (lc_name, site, entries) in fixtures.items():
        company = db.query(models.Company).filter_by(name=company_name).one()
        collector = db.query(LogCollector).filter_by(company_id=company.id, name=lc_name).first()
        if not collector:
            collector = LogCollector(company_id=company.id, name=lc_name, site=site)
            db.add(collector)
            db.flush()
        for ip, hostname, asset_type, event_type, message in entries:
            asset = db.query(CustomerAsset).filter_by(company_id=company.id, ip_address=ip).first()
            if not asset:
                asset = CustomerAsset(company_id=company.id, ip_address=ip, hostname=hostname, asset_type=asset_type)
                db.add(asset)
                db.flush()
            exists = db.query(CustomerLog).filter_by(
                company_id=company.id, asset_id=asset.id, collector_id=collector.id,
                event_type=event_type, message=message).first()
            if not exists:
                db.add(CustomerLog(company_id=company.id, asset_id=asset.id, collector_id=collector.id,
                                   event_type=event_type, message=message))
    db.commit()
print("Customer telemetry demo data seeded")
