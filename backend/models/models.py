from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, index=True)
    contact_email = Column(String)
    phone = Column(String, nullable=True)
    sla_plan = Column(String, default="Standard")
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="customer")
    tickets = relationship("Ticket", back_populates="customer")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="CUSTOMER") # CUSTOMER, SUPPORT_AGENT, ADMIN
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="users")
    tickets_created = relationship("Ticket", foreign_keys='Ticket.created_by', back_populates="creator")
    tickets_assigned = relationship("Ticket", foreign_keys='Ticket.assigned_to', back_populates="assignee")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    status = Column(String, default="Active")

    tickets = relationship("Ticket", back_populates="category")
    knowledge_articles = relationship("KnowledgeArticle", back_populates="category")

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    created_by = Column(Integer, ForeignKey("users.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    subject = Column(String)
    description = Column(Text)
    priority = Column(String, default="3 - Normal")
    status = Column(String, default="OPEN")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="tickets")
    creator = relationship("User", foreign_keys=[created_by], back_populates="tickets_created")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="tickets_assigned")
    category = relationship("Category", back_populates="tickets")
    messages = relationship("TicketMessage", back_populates="ticket")

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    message = Column(Text)
    is_internal = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="messages")
    sender = relationship("User")

class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    status = Column(String, default="Published")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="knowledge_articles")