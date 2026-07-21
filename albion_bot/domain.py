from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EventStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SlotDefinition:
    key: str
    label: str
    emoji: str
    capacity: int


@dataclass(frozen=True, slots=True)
class Signup:
    user_id: int
    slot_key: str
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class GuildEvent:
    id: int
    guild_id: int
    channel_id: int
    message_id: int | None
    creator_id: int
    activity: str
    title: str
    description: str
    starts_at: datetime
    status: EventStatus
    slots: tuple[SlotDefinition, ...]
    signups: tuple[Signup, ...]


class SignupResult(StrEnum):
    JOINED = "joined"
    MOVED = "moved"
    ALREADY_JOINED = "already_joined"
    FULL = "full"
    EVENT_CLOSED = "event_closed"
    SLOT_NOT_FOUND = "slot_not_found"

