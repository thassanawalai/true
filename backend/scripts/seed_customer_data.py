"""Idempotent demo telemetry seed. Run from backend: PYTHONPATH=. python scripts/seed_customer_data.py"""
from core.database import Base, engine, SessionLocal
from models import models  # noqa: F401; register existing tables
from models.customer_data import CustomerAsset, LogCollector, CustomerLog

Base.metadata.create_all(bind=engine)
from core.demo_telemetry import FIXTURES as fixtures

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
