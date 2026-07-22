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
        "hg",
        "Hellgate 5v5",
        0xD7263D,
        (
            _slot("frontline", "Frontline", "🛡️", 1),
            _slot("healer", "Healer", "💚", 1),
            _slot("dps", "DPS/Support", "⚔️", 3),
        ),
    ),
    "arena": ActivityPreset(
        "arena",
        "Arena de Cristal",
        0x6C5CE7,
        (
            _slot("frontline", "Frontline", "🛡️", 1),
            _slot("healer", "Healer", "💚", 1),
            _slot("dps", "DPS/Support", "⚔️", 3),
        ),
    ),
    "crystal": ActivityPreset(
        "crystal",
        "Liga de Cristal 5v5",
        0x9B59B6,
        (
            _slot("frontline", "Frontline", "🛡️", 1),
            _slot("healer", "Healer", "💚", 1),
            _slot("dps", "DPS/Support", "⚔️", 3),
            _slot("suplente", "Suplentes", "🔄", 2),
        ),
    ),
    "avalon": ActivityPreset(
        "avalon",
        "Caminos Avalonianos",
        0xE74C3C,
        (
            _slot("caller", "Caller", "📣", 1),
            _slot("healer", "Healer", "💚", 1),
            _slot("support", "Soporte", "✨", 1),
            _slot("dps", "DPS", "⚔️", 4),
        ),
    ),
    "static": ActivityPreset(
        "static",
        "Estática",
        0xF39C12,
        (
            _slot("puller", "Puller/Frontline", "🛡️", 1),
            _slot("healer", "Healer", "💚", 1),
            _slot("support", "Soporte", "✨", 1),
            _slot("dps", "DPS", "⚔️", 4),
        ),
    ),
    "group": ActivityPreset(
        "group",
        "Mazmorra Grupal",
        0x3498DB,
        (
            _slot("tank", "Tanque", "🛡️", 1),
            _slot("healer", "Healer", "💚", 1),
            _slot("dps", "DPS/Support", "⚔️", 3),
        ),
    ),
}


ROAD_SLOTS: dict[str, tuple[SlotDefinition, ...]] = {
    "pve": (
        _slot("tank", "Tanque", "🛡️", 1),
        _slot("healer", "Healer", "💚", 1),
        _slot("support", "Soporte", "✨", 1),
        _slot("dps", "DPS", "⚔️", 4),
    ),
    "pvp": ACTIVITIES["avalon"].slots,
    "tracking": (
        _slot("tracker", "Tracker", "🐾", 1),
        _slot("healer", "Healer", "💚", 1),
        _slot("dps", "DPS/Support", "⚔️", 5),
    ),
    "transport": (
        _slot("scout", "Scout", "👁️", 1),
        _slot("escort", "Escolta", "🛡️", 2),
        _slot("transporter", "Transportistas", "📦", 4),
    ),
}
