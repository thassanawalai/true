"""Bounded, single-process, non-durable live transport. Reads never extend TTL."""
from threading import RLock
from time import monotonic
from fastapi import HTTPException

TTL_SECONDS = 30 * 60
MAX_ROOMS = 1000
MAX_MESSAGES = 200
lock = RLock()
rooms = {}
answering = set()


def purge():
    # Caller holds lock. No message content is logged or written to disk.
    now = monotonic()
    for room_id in list(rooms):
        if rooms[room_id]['deadline'] <= now:
            del rooms[room_id]


def capacity(room, additional):
    if len(room['messages']) + additional > MAX_MESSAGES:
        raise HTTPException(409, 'Temporary chat is full. Create a ticket or start a new chat.')
