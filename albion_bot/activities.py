from __future__ import annotations

from dataclasses import dataclass

from .domain import SlotDefinition


@dataclass(frozen=True, slots=True)
class ActivityPreset:
    key: str
    label: str
    color: int
    slots: tuple[SlotDefinition, ...]


def _slot(key: str, label: str, emoji: str, capacity: int) -> SlotDefinition:
    return SlotDefinition(key, label, emoji, capacity)


ACTIVITIES: dict[str, ActivityPreset] = {
    "hg": ActivityPreset(
        "hg", "Hellgate", 0xD7263D,
        (_slot("healer", "Healer", "💚", 1), _slot("dps", "DPS", "⚔️", 1)),
    ),
    "arena": ActivityPreset(
        "arena", "Arena de Cristal", 0x6C5CE7,
        (_slot("tank", "Tanque", "🛡️", 1), _slot("healer", "Healer", "💚", 1),
         _slot("dps", "DPS", "⚔️", 3)),
    ),
    "crystal": ActivityPreset(
        "crystal", "Liga de Cristal", 0x9B59B6,
        (_slot("tank", "Tanque", "🛡️", 1), _slot("healer", "Healer", "💚", 1),
         _slot("support", "Soporte", "✨", 1), _slot("dps", "DPS", "⚔️", 2)),
    ),
    "avalon": ActivityPreset(
        "avalon", "Caminos Avalonianos", 0xE74C3C,
        (_slot("caller", "Caller", "📣", 1), _slot("offtank", "Offtank", "🛡️", 1),
         _slot("healer", "Healer", "💚", 2), _slot("support", "Soporte", "✨", 2),
         _slot("dps", "DPS", "⚔️", 6)),
    ),
    "tracking": ActivityPreset(
        "tracking", "Rastreo", 0x27AE60,
        (_slot("tank", "Tanque", "🛡️", 1), _slot("healer", "Healer", "💚", 1),
         _slot("dps", "DPS", "⚔️", 3)),
    ),
    "static": ActivityPreset(
        "static", "Estática", 0xF39C12,
        (_slot("tank", "Tanque", "🛡️", 1), _slot("healer", "Healer", "💚", 1),
         _slot("support", "Soporte", "✨", 1), _slot("dps", "DPS", "⚔️", 4)),
    ),
    "group": ActivityPreset(
        "group", "Mazmorra grupal", 0x3498DB,
        (_slot("tank", "Tanque", "🛡️", 1), _slot("healer", "Healer", "💚", 1),
         _slot("dps", "DPS", "⚔️", 3)),
    ),
}

