import enum
from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base

# ==========================================
# 1. ENUMS
# ==========================================
class RoleEnum(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    SUPPORT = "SUPPORT"
    ADMIN = "ADMIN"

class ImpactEnum(str, enum.Enum):
    EXTENSIVE = "EXTENSIVE"
    SIGNIFICANT = "SIGNIFICANT"
    MODERATE = "MODERATE"
    MINOR = "MINOR"

class UrgencyEnum(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class PriorityEnum(str, enum.Enum):
    P1 = "P1" # Critical
    P2 = "P2" # High
    P3 = "P3" # Medium
    P4 = "P4" # Low

class SLAStatusEnum(str, enum.Enum):
    MET = "MET"
    BREACHED = "BREACHED"
    IN_PROGRESS = "IN_PROGRESS"

# ==========================================
# 2. CORE ENTITIES (MULTI-TENANT & USERS)
# ==========================================
class Company(Base):
    __tablename__ = "companies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="company")
    tickets = relationship("Ticket", back_populates="company")

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.CUSTOMER, nullable=False)
    
    # Multi-tenant link: Every user belongs to a company (Support agents can belong to an internal company)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    company = relationship("Company", back_populates="users")
    
    created_at = Column(DateTime, default=datetime.utcnow)

class TicketCategory(Base):
    __tablename__ = "ticket_categories"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)

# ==========================================
# 3. ITSM & TICKET MANAGEMENT
# ==========================================
class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    priority = Column(Enum(PriorityEnum), nullable=False, unique=True)
    time_to_own_minutes = Column(Integer, nullable=False)
    time_to_resolve_minutes = Column(Integer, nullable=False)

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number = Column(String, nullable=False, unique=True, index=True)
    
    # Relationships
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True) # None until assigned
    category_id = Column(UUID(as_uuid=True), ForeignKey("ticket_categories.id"), nullable=False)
    sla_policy_id = Column(UUID(as_uuid=True), ForeignKey("sla_policies.id"), nullable=False)
    
    # Content
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    
    # Metrics & Matrix
    impact = Column(Enum(ImpactEnum), nullable=False)
    urgency = Column(Enum(UrgencyEnum), nullable=False)
    priority = Column(Enum(PriorityEnum), nullable=False)
    status = Column(String, default="NEW", nullable=False) # e.g., NEW, ASSIGNED, IN_PROGRESS, RESOLVED, CLOSED
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Navigational Properties
    company = relationship("Company", back_populates="tickets")
    requester = relationship("User", foreign_keys=[requester_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    sla_tracking = relationship("TicketSLA", back_populates="ticket", uselist=False, cascade="all, delete-orphan")
    comments = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")
    audit_logs = relationship("TicketAuditLog", back_populates="ticket", cascade="all, delete-orphan")

# ==========================================
# 4. TRACKING & HISTORY
# ==========================================
class TicketSLA(Base):
    __tablename__ = "ticket_slas"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, unique=True)
    sla_policy_id = Column(UUID(as_uuid=True), ForeignKey("sla_policies.id"), nullable=False)
    
    # Deadlines
    ownership_due_at = Column(DateTime, nullable=False)
    resolution_due_at = Column(DateTime, nullable=False)
    
    # Actual completion times
    owned_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    ticket = relationship("Ticket", back_populates="sla_tracking")

class TicketComment(Base):
    __tablename__ = "ticket_comments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    message = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False) # True = Support internal note, False = Visible to customer
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="comments")
    sender = relationship("User", foreign_keys=[sender_id])

class TicketAuditLog(Base):
    __tablename__ = "ticket_audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    action = Column(String, nullable=False) # e.g., "STATUS_CHANGED", "ASSIGNED", "PRIORITY_UPDATED"
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="audit_logs")
    user = relationship("User", foreign_keys=[user_id])