from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata
from zoneinfo import ZoneInfo

from .domain import SlotDefinition


DATE_FORMATS = ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M")
SLOT_PATTERN = re.compile(r"^\s*([^:=]+)\s*[:=]\s*(\d+)\s*$")
SLOT_EMOJIS = {
    "caller": "📣", "tank": "🛡️", "tanque": "🛡️", "offtank": "🛡️",
    "healer": "💚", "heal": "💚", "support": "✨", "soporte": "✨",
    "dps": "⚔️", "meledps": "⚔️", "mele-dps": "⚔️", "sc": "🔷",
    "ironroot": "🌿", "martillo": "🔨", "dawnsong": "🔥",
    "rotcaller": "🌀", "shadowcaller": "🟣", "frost": "❄️",
}


def parse_local_datetime(value: str, local_timezone: ZoneInfo) -> datetime:
    cleaned = value.strip()
    for date_format in DATE_FORMATS:
        try:
            local = datetime.strptime(cleaned, date_format).replace(tzinfo=local_timezone)
            return local.astimezone(timezone.utc)
        except ValueError:
            continue
    raise ValueError("Usa una fecha como `20/07/2026 15:30` o `2026-07-20 15:30`.")


def parse_slots(value: str) -> tuple[SlotDefinition, ...]:
    if not value.strip():
        raise ValueError("La lista de cupos está vacía.")
    slots: list[SlotDefinition] = []
    keys: set[str] = set()
    for part in value.split(","):
        match = SLOT_PATTERN.match(part)
        if not match:
            raise ValueError(f"Cupo inválido: `{part.strip()}`. Usa `tanque:1, healer:1, dps:3`.")
        label = match.group(1).strip()
        capacity = int(match.group(2))
        if not 1 <= capacity <= 99:
            raise ValueError("Cada cupo debe estar entre 1 y 99.")
        key = slugify(label)
        if not key or key in keys:
            raise ValueError(f"El rol `{label}` está repetido o no es válido.")
        keys.add(key)
        slots.append(SlotDefinition(key, label.title(), SLOT_EMOJIS.get(key, "⭐"), capacity))
    if len(slots) > 20:
        raise ValueError("Discord permite un máximo práctico de 20 roles por evento.")
    return tuple(slots)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")[:30]
