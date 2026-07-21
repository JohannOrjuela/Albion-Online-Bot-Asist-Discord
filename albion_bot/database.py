from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import Iterator

from .domain import (
    AlbionBuild,
    CompositionTemplate,
    EventStatus,
    GuildEvent,
    Signup,
    SignupResult,
    SlotDefinition,
)


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS guild_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER,
    creator_id INTEGER NOT NULL,
    activity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    starts_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES guild_events(id) ON DELETE CASCADE,
    role_key TEXT NOT NULL,
    label TEXT NOT NULL,
    emoji TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    position INTEGER NOT NULL,
    UNIQUE(event_id, role_key)
);
CREATE TABLE IF NOT EXISTS event_signups (
    event_id INTEGER NOT NULL REFERENCES guild_events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL REFERENCES event_slots(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    PRIMARY KEY(event_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_events_status ON guild_events(status, starts_at);
CREATE INDEX IF NOT EXISTS idx_signups_slot ON event_signups(slot_id);

CREATE TABLE IF NOT EXISTS builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL COLLATE NOCASE,
    activity TEXT NOT NULL DEFAULT '',
    weapon TEXT NOT NULL,
    offhand TEXT NOT NULL DEFAULT '',
    head TEXT NOT NULL,
    chest TEXT NOT NULL,
    shoes TEXT NOT NULL,
    cape TEXT NOT NULL DEFAULT '',
    food TEXT NOT NULL DEFAULT '',
    potion TEXT NOT NULL DEFAULT '',
    abilities TEXT NOT NULL DEFAULT '',
    minimum_ip INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS composition_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL COLLATE NOCASE,
    activity TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(guild_id, name)
);

CREATE TABLE IF NOT EXISTS template_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES composition_templates(id) ON DELETE CASCADE,
    role_key TEXT NOT NULL,
    label TEXT NOT NULL,
    emoji TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    position INTEGER NOT NULL,
    build_id INTEGER REFERENCES builds(id) ON DELETE SET NULL,
    UNIQUE(template_id, role_key)
);

CREATE TABLE IF NOT EXISTS guild_role_emojis (
    guild_id INTEGER NOT NULL,
    role_key TEXT NOT NULL,
    emoji TEXT NOT NULL,
    PRIMARY KEY(guild_id, role_key)
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._lock, self._connection() as connection:
            connection.executescript(SCHEMA)
            event_slot_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(event_slots)")
            }
            if "build_id" not in event_slot_columns:
                connection.execute(
                    "ALTER TABLE event_slots ADD COLUMN build_id INTEGER REFERENCES builds(id)"
                )

    def create_event(
        self, *, guild_id: int, channel_id: int, creator_id: int, activity: str,
        title: str, description: str, starts_at: datetime,
        slots: tuple[SlotDefinition, ...],
    ) -> GuildEvent:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """INSERT INTO guild_events(
                    guild_id, channel_id, creator_id, activity, title,
                    description, starts_at, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (guild_id, channel_id, creator_id, activity, title, description,
                 starts_at.astimezone(timezone.utc).isoformat(), EventStatus.OPEN.value, now),
            )
            event_id = int(cursor.lastrowid)
            connection.executemany(
                """INSERT INTO event_slots(
                    event_id, role_key, label, emoji, capacity, position, build_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(event_id, slot.key, slot.label, slot.emoji, slot.capacity, index, slot.build_id)
                 for index, slot in enumerate(slots)],
            )
        event = self.get_event(event_id)
        if event is None:
            raise RuntimeError("No fue posible leer el evento recién creado.")
        return event

    def set_event_message(self, event_id: int, message_id: int) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                "UPDATE guild_events SET message_id = ? WHERE id = ?", (message_id, event_id)
            )

    def set_event_status(self, event_id: int, status: EventStatus) -> bool:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "UPDATE guild_events SET status = ? WHERE id = ?", (status.value, event_id)
            )
            return cursor.rowcount > 0

    def signup(self, event_id: int, user_id: int, role_key: str) -> SignupResult:
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event_row = connection.execute(
                "SELECT status FROM guild_events WHERE id = ?", (event_id,)
            ).fetchone()
            if event_row is None or event_row["status"] != EventStatus.OPEN.value:
                return SignupResult.EVENT_CLOSED
            slot_row = connection.execute(
                "SELECT id, capacity FROM event_slots WHERE event_id = ? AND role_key = ?",
                (event_id, role_key),
            ).fetchone()
            if slot_row is None:
                return SignupResult.SLOT_NOT_FOUND
            existing = connection.execute(
                """SELECT s.role_key FROM event_signups es
                   JOIN event_slots s ON s.id = es.slot_id
                   WHERE es.event_id = ? AND es.user_id = ?""",
                (event_id, user_id),
            ).fetchone()
            if existing is not None and existing["role_key"] == role_key:
                return SignupResult.ALREADY_JOINED
            count = connection.execute(
                "SELECT COUNT(*) AS total FROM event_signups WHERE slot_id = ?",
                (slot_row["id"],),
            ).fetchone()["total"]
            if count >= slot_row["capacity"]:
                return SignupResult.FULL
            now = datetime.now(timezone.utc).isoformat()
            if existing is None:
                connection.execute(
                    "INSERT INTO event_signups(event_id, user_id, slot_id, joined_at) VALUES (?, ?, ?, ?)",
                    (event_id, user_id, slot_row["id"], now),
                )
                return SignupResult.JOINED
            connection.execute(
                """UPDATE event_signups SET slot_id = ?, joined_at = ?
                   WHERE event_id = ? AND user_id = ?""",
                (slot_row["id"], now, event_id, user_id),
            )
            return SignupResult.MOVED

    def leave_event(self, event_id: int, user_id: int) -> bool:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM event_signups WHERE event_id = ? AND user_id = ?",
                (event_id, user_id),
            )
            return cursor.rowcount > 0

    def get_event(self, event_id: int) -> GuildEvent | None:
        with self._lock, self._connection() as connection:
            event_row = connection.execute(
                "SELECT * FROM guild_events WHERE id = ?", (event_id,)
            ).fetchone()
            if event_row is None:
                return None
            slot_rows = connection.execute(
                """SELECT s.*, b.name AS build_name
                   FROM event_slots s LEFT JOIN builds b ON b.id = s.build_id
                   WHERE s.event_id = ? ORDER BY s.position""",
                (event_id,),
            ).fetchall()
            signup_rows = connection.execute(
                """SELECT es.user_id, es.joined_at, s.role_key
                   FROM event_signups es JOIN event_slots s ON s.id = es.slot_id
                   WHERE es.event_id = ? ORDER BY es.joined_at""",
                (event_id,),
            ).fetchall()

        return GuildEvent(
            id=event_row["id"], guild_id=event_row["guild_id"],
            channel_id=event_row["channel_id"], message_id=event_row["message_id"],
            creator_id=event_row["creator_id"], activity=event_row["activity"],
            title=event_row["title"], description=event_row["description"],
            starts_at=datetime.fromisoformat(event_row["starts_at"]),
            status=EventStatus(event_row["status"]),
            slots=tuple(
                SlotDefinition(
                    row["role_key"], row["label"], row["emoji"], row["capacity"],
                    row["build_id"], row["build_name"],
                )
                for row in slot_rows
            ),
            signups=tuple(
                Signup(row["user_id"], row["role_key"], datetime.fromisoformat(row["joined_at"]))
                for row in signup_rows
            ),
        )

    def get_open_events(self) -> list[GuildEvent]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT id FROM guild_events WHERE status = ? AND message_id IS NOT NULL",
                (EventStatus.OPEN.value,),
            ).fetchall()
        return [event for row in rows if (event := self.get_event(row["id"])) is not None]

    def save_build(
        self, *, guild_id: int, name: str, activity: str, weapon: str,
        offhand: str, head: str, chest: str, shoes: str, cape: str,
        food: str, potion: str, abilities: str, minimum_ip: int | None,
        notes: str,
    ) -> AlbionBuild:
        now = datetime.now(timezone.utc).isoformat()
        values = (
            guild_id, name.strip(), activity.strip(), weapon.strip(), offhand.strip(),
            head.strip(), chest.strip(), shoes.strip(), cape.strip(), food.strip(),
            potion.strip(), abilities.strip(), minimum_ip, notes.strip(), now, now,
        )
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO builds(
                    guild_id, name, activity, weapon, offhand, head, chest, shoes,
                    cape, food, potion, abilities, minimum_ip, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, name) DO UPDATE SET
                    activity=excluded.activity, weapon=excluded.weapon,
                    offhand=excluded.offhand, head=excluded.head, chest=excluded.chest,
                    shoes=excluded.shoes, cape=excluded.cape, food=excluded.food,
                    potion=excluded.potion, abilities=excluded.abilities,
                    minimum_ip=excluded.minimum_ip, notes=excluded.notes,
                    updated_at=excluded.updated_at""",
                values,
            )
        build = self.get_build(guild_id, name)
        if build is None:
            raise RuntimeError("No fue posible leer la build recién guardada.")
        return build

    def get_build(self, guild_id: int, name: str) -> AlbionBuild | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM builds WHERE guild_id = ? AND name = ? COLLATE NOCASE",
                (guild_id, name.strip()),
            ).fetchone()
        return self._build_from_row(row) if row else None

    def get_build_by_id(self, build_id: int) -> AlbionBuild | None:
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
        return self._build_from_row(row) if row else None

    def list_builds(self, guild_id: int) -> list[AlbionBuild]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM builds WHERE guild_id = ? ORDER BY name COLLATE NOCASE",
                (guild_id,),
            ).fetchall()
        return [self._build_from_row(row) for row in rows]

    def delete_build(self, guild_id: int, name: str) -> bool:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM builds WHERE guild_id = ? AND name = ? COLLATE NOCASE",
                (guild_id, name.strip()),
            )
            return cursor.rowcount > 0

    @staticmethod
    def _build_from_row(row: sqlite3.Row) -> AlbionBuild:
        return AlbionBuild(
            id=row["id"], guild_id=row["guild_id"], name=row["name"],
            activity=row["activity"], weapon=row["weapon"], offhand=row["offhand"],
            head=row["head"], chest=row["chest"], shoes=row["shoes"], cape=row["cape"],
            food=row["food"], potion=row["potion"], abilities=row["abilities"],
            minimum_ip=row["minimum_ip"], notes=row["notes"],
        )

    def create_template(
        self, guild_id: int, name: str, activity: str, description: str
    ) -> CompositionTemplate:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO composition_templates(
                    guild_id, name, activity, description, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, name) DO UPDATE SET
                    activity=excluded.activity, description=excluded.description""",
                (guild_id, name.strip(), activity, description.strip(), now),
            )
        template = self.get_template(guild_id, name)
        if template is None:
            raise RuntimeError("No fue posible leer la plantilla recién guardada.")
        return template

    def upsert_template_slot(
        self, *, guild_id: int, template_name: str, role_key: str, label: str,
        emoji: str, capacity: int, build_id: int | None,
    ) -> CompositionTemplate | None:
        with self._lock, self._connection() as connection:
            template = connection.execute(
                """SELECT id FROM composition_templates
                   WHERE guild_id = ? AND name = ? COLLATE NOCASE""",
                (guild_id, template_name.strip()),
            ).fetchone()
            if template is None:
                return None
            existing = connection.execute(
                "SELECT position FROM template_slots WHERE template_id = ? AND role_key = ?",
                (template["id"], role_key),
            ).fetchone()
            if existing is None:
                position = connection.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 AS next FROM template_slots WHERE template_id = ?",
                    (template["id"],),
                ).fetchone()["next"]
            else:
                position = existing["position"]
            connection.execute(
                """INSERT INTO template_slots(
                    template_id, role_key, label, emoji, capacity, position, build_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(template_id, role_key) DO UPDATE SET
                    label=excluded.label, emoji=excluded.emoji,
                    capacity=excluded.capacity, build_id=excluded.build_id""",
                (template["id"], role_key, label, emoji, capacity, position, build_id),
            )
        return self.get_template(guild_id, template_name)

    def get_template(self, guild_id: int, name: str) -> CompositionTemplate | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                """SELECT * FROM composition_templates
                   WHERE guild_id = ? AND name = ? COLLATE NOCASE""",
                (guild_id, name.strip()),
            ).fetchone()
            if row is None:
                return None
            slot_rows = connection.execute(
                """SELECT s.*, b.name AS build_name
                   FROM template_slots s LEFT JOIN builds b ON b.id = s.build_id
                   WHERE s.template_id = ? ORDER BY s.position""",
                (row["id"],),
            ).fetchall()
        return CompositionTemplate(
            id=row["id"], guild_id=row["guild_id"], name=row["name"],
            activity=row["activity"], description=row["description"],
            slots=tuple(
                SlotDefinition(
                    slot["role_key"], slot["label"], slot["emoji"], slot["capacity"],
                    slot["build_id"], slot["build_name"],
                )
                for slot in slot_rows
            ),
        )

    def list_templates(self, guild_id: int) -> list[CompositionTemplate]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT name FROM composition_templates WHERE guild_id = ? ORDER BY name COLLATE NOCASE",
                (guild_id,),
            ).fetchall()
        return [template for row in rows if (template := self.get_template(guild_id, row["name"]))]

    def delete_template(self, guild_id: int, name: str) -> bool:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM composition_templates WHERE guild_id = ? AND name = ? COLLATE NOCASE",
                (guild_id, name.strip()),
            )
            return cursor.rowcount > 0

    def set_role_emoji(self, guild_id: int, role_key: str, emoji: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO guild_role_emojis(guild_id, role_key, emoji) VALUES (?, ?, ?)
                   ON CONFLICT(guild_id, role_key) DO UPDATE SET emoji=excluded.emoji""",
                (guild_id, role_key, emoji),
            )

    def get_role_emojis(self, guild_id: int) -> dict[str, str]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT role_key, emoji FROM guild_role_emojis WHERE guild_id = ?",
                (guild_id,),
            ).fetchall()
        return {row["role_key"]: row["emoji"] for row in rows}
