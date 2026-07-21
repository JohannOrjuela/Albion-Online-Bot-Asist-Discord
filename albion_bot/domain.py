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
    build_id: int | None = None
    build_name: str | None = None


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


@dataclass(frozen=True, slots=True)
class AlbionBuild:
    id: int
    guild_id: int
    name: str
    activity: str
    weapon: str
    offhand: str
    head: str
    chest: str
    shoes: str
    cape: str
    food: str
    potion: str
    abilities: str
    minimum_ip: int | None
    notes: str

    @property
    def equipment(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Arma", self.weapon),
            ("Mano secundaria", self.offhand),
            ("Casco", self.head),
            ("Pechera", self.chest),
            ("Botas", self.shoes),
            ("Capa", self.cape),
            ("Comida", self.food),
            ("Poción", self.potion),
        )


@dataclass(frozen=True, slots=True)
class CompositionTemplate:
    id: int
    guild_id: int
    name: str
    activity: str
    description: str
    slots: tuple[SlotDefinition, ...]
