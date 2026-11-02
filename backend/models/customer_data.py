"""Demo customer assets, log collectors and events. All records belong to a company."""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base

class CustomerAsset(Base):
    __tablename__ = "customer_assets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    hostname = Column(String(255), nullable=False)
    asset_type = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "ip_address", name="uq_asset_company_ip"),)

class LogCollector(Base):
    __tablename__ = "log_collectors"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    site = Column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_collector_company_name"),)

class CustomerLog(Base):
    __tablename__ = "customer_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("customer_assets.id"), nullable=False)
    collector_id = Column(UUID(as_uuid=True), ForeignKey("log_collectors.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)
