"""Only ticket-linked conversations are durable. Unticketed rooms never use ORM."""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base


class ChatRoom(Base):
    __tablename__ = 'chat_rooms'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False, index=True)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    messages = relationship('RoomMessage', cascade='all, delete-orphan', order_by='RoomMessage.sequence')


class RoomMessage(Base):
    __tablename__ = 'room_messages'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey('chat_rooms.id', ondelete='CASCADE'), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    role = Column(String, nullable=False)  # customer, assistant, support
    sender_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    sender_name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
