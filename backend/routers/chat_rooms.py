"""Private live rooms, SOC replies, and atomic promotion to ticket history."""
from datetime import datetime, timedelta
from time import monotonic
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from core.database import get_db
from core.demo_auth import current_user, internal
from models.models import Company, User, Ticket
from models.chat import ChatRoom, RoomMessage
from services.support_answers import answer_question
from routers.customer_data import authorized_company
from services import temporary_chat as live
from services.ticket_service import assess_ticket, create_ticket_from_ai

router = APIRouter(prefix='/api/chat-rooms', tags=['Private Chat'])


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: str = Field(min_length=1, max_length=1000)


class LinkInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(default='Created from private chat. History is available to the chat owner and SOC only.', max_length=5000)


def check_owner(owner_id, company_id, user):
    if not internal(user) and (owner_id != user.id or company_id != user.company_id):
        raise HTTPException(404, 'Chat room not found')


def durable(db, room_id, user):
    query = db.query(ChatRoom).filter(ChatRoom.id == room_id)
    if not internal(user):
        query = query.filter(ChatRoom.owner_id == user.id, ChatRoom.company_id == user.company_id)
    return query.first()


def temporary(room_id, user):
    live.purge()
    room = live.rooms.get(room_id)
    if not room:
        raise HTTPException(404, 'Chat room expired or unavailable. Open a new private chat.')
    check_owner(room['owner_id'], room['company_id'], user)
    return room


def message_dict(message):
    return {key: getattr(message, key) for key in ('id', 'role', 'sender_id', 'sender_name', 'content', 'created_at')}


def snapshot(db, room, include_messages=True):
    if isinstance(room, dict):
        result = {key: room[key] for key in ('id', 'owner_id', 'company_id', 'created_at')}
        result.update(ticket_id=None, ticket_number=None, temporary=True,
                      expires_at=datetime.utcnow() + timedelta(seconds=max(0, room['deadline'] - monotonic())))
        messages = room['messages']
    else:
        ticket = db.get(Ticket, room.ticket_id)
        result = {key: getattr(room, key) for key in ('id', 'owner_id', 'company_id', 'created_at', 'ticket_id')}
        result.update(ticket_number=ticket.ticket_number, temporary=False, expires_at=None)
        messages = [message_dict(message) for message in room.messages] if include_messages else []
    owner = db.get(User, result['owner_id'])
    result['owner_name'] = owner.full_name
    if include_messages:
        result['messages'] = messages
    return result


def new_message(role, user, content):
    return {'id': uuid4(), 'role': role, 'sender_id': user.id if user else None,
            'sender_name': user.full_name if user else 'Demo Chatbot', 'content': content,
            'created_at': datetime.utcnow()}


@router.get('')
def list_rooms(company_id: UUID | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    if company_id is not None:
        authorized_company(db, user, company_id)
    query = db.query(ChatRoom)
    if not internal(user):
        query = query.filter(ChatRoom.owner_id == user.id, ChatRoom.company_id == user.company_id)
    if company_id:
        query = query.filter(ChatRoom.company_id == company_id)
    with live.lock:
        live.purge()
        active = [room for room in live.rooms.values()
                  if (internal(user) or (room['owner_id'] == user.id and room['company_id'] == user.company_id))
                  and (not company_id or room['company_id'] == company_id)]
        return [snapshot(db, room, False) for room in active] + [snapshot(db, room, False) for room in query.order_by(ChatRoom.created_at.desc()).all()]


@router.post('')
def open_room(db: Session = Depends(get_db), user=Depends(current_user)):
    if internal(user):
        raise HTTPException(403, 'Only customers can open a private chat')
    with live.lock:
        live.purge()
        for room in live.rooms.values():
            if room['owner_id'] == user.id and room['company_id'] == user.company_id:
                return snapshot(db, room)
        if len(live.rooms) >= live.MAX_ROOMS:
            raise HTTPException(503, 'Live chat capacity reached. Please try later.')
        room = {'id': uuid4(), 'owner_id': user.id, 'company_id': user.company_id,
                'created_at': datetime.utcnow(), 'deadline': monotonic() + live.TTL_SECONDS, 'messages': []}
        live.rooms[room['id']] = room
        return snapshot(db, room)


@router.get('/by-ticket/{ticket_id}')
def ticket_history(ticket_id: UUID, db: Session = Depends(get_db), user=Depends(current_user)):
    query = db.query(ChatRoom).filter(ChatRoom.ticket_id == ticket_id)
    if not internal(user):
        query = query.filter(ChatRoom.owner_id == user.id, ChatRoom.company_id == user.company_id)
    room = query.first()
    if not room:
        raise HTTPException(404, 'No chat history available to this user')
    return snapshot(db, room)


@router.get('/{room_id}')
def read_room(room_id: UUID, db: Session = Depends(get_db), user=Depends(current_user)):
    with live.lock:
        room = durable(db, room_id, user)
        return snapshot(db, room if room else temporary(room_id, user))


@router.delete('/{room_id}')
def discard_room(room_id: UUID, user=Depends(current_user)):
    with live.lock:
        room = temporary(room_id, user)
        if internal(user):
            raise HTTPException(403, 'Only the chat owner can discard temporary chat')
        del live.rooms[room['id']]
        return {'discarded': True}


def append_messages(db, saved, room, additions):
    if saved:
        sequence = len(saved.messages)
        for index, message in enumerate(additions, start=sequence):
            db.add(RoomMessage(room_id=saved.id, sequence=index, **message))
        db.commit()
        db.expire(saved, ['messages'])
        return snapshot(db, saved)
    live.capacity(room, len(additions))
    room['messages'].extend(additions)
    room['deadline'] = monotonic() + live.TTL_SECONDS
    return snapshot(db, room)


@router.post('/{room_id}/messages')
def send_message(room_id: UUID, payload: MessageInput, db: Session = Depends(get_db), user=Depends(current_user)):
    content = payload.content.strip()
    if not content:
        raise HTTPException(422, 'Message cannot be blank')
    with live.lock:
        saved = durable(db, room_id, user)
        room = saved if saved else temporary(room_id, user)
        messages = ([message_dict(message) for message in saved.messages] if saved else room['messages'])
        if internal(user):
            if not any(message['role'] == 'assistant' for message in messages):
                raise HTTPException(409, 'Customer must receive the chatbot answer first')
            return append_messages(db, saved, room, [new_message('support', user, content)])
        if room_id in live.answering:
            raise HTTPException(409, 'A chatbot answer is already in progress for this room')
        if not saved:
            live.capacity(room, 2)  # Reject before any potential inference call.
        history = [dict(message) for message in messages[-6:]]
        live.answering.add(room_id)
    try:
        # Never hold the shared store lock over network IO: SOC replies and other
        # rooms continue working while this room waits for Gemini or fallback.
        answer = answer_question(content, db, user, history=history)
        with live.lock:
            db.expire_all()
            saved = durable(db, room_id, user)
            room = saved if saved else temporary(room_id, user)
            additions = [new_message('customer', user, content), new_message('assistant', None, answer['answer'])]
            return append_messages(db, saved, room, additions)
    finally:
        with live.lock:
            live.answering.discard(room_id)


@router.post('/{room_id}/ticket')
def link_ticket(room_id: UUID, payload: LinkInput, db: Session = Depends(get_db), user=Depends(current_user)):
    if internal(user):
        raise HTTPException(403, 'Only the customer can confirm ticket creation')
    if not payload.subject.strip():
        raise HTTPException(422, 'Subject cannot be blank')
    with live.lock:
        saved = durable(db, room_id, user)
        if saved:
            return snapshot(db, saved)  # Retry is idempotent after a lost response.
        room = temporary(room_id, user)
        if not any(message['role'] == 'assistant' for message in room['messages']):
            raise HTTPException(409, 'Ask the chatbot before creating a ticket from chat')
        if room_id in live.promoting:
            raise HTTPException(409, 'Ticket creation already in progress')
        live.promoting.add(room_id)
    try:
        company = db.get(Company, user.company_id)
        assessment = assess_ticket(payload.subject.strip(), payload.description, user, company.name)
        with live.lock:
            room = temporary(room_id, user)
            return promote(db, room, user, payload, assessment)
    finally:
        with live.lock:
            live.promoting.discard(room_id)


def promote(db, room, user, payload, assessment):
    room_id = room['id']
    result = create_ticket_from_ai(db, issue_description=payload.description, subject=payload.subject.strip(),
                                  company_id=user.company_id, requester_id=user.id, commit=False, assessed=assessment)
    if not result['success']:
        raise HTTPException(500, 'Unable to create ticket')
    try:
        saved = ChatRoom(id=room_id, owner_id=user.id, company_id=user.company_id,
                         ticket_id=result['ticket_id'], created_at=room['created_at'])
        db.add(saved)
        db.flush()
        for index, message in enumerate(room['messages']):
            db.add(RoomMessage(room_id=room_id, sequence=index, **message))
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, 'Unable to save ticket and history; temporary chat is unchanged')
    del live.rooms[room_id]
    return snapshot(db, saved)
