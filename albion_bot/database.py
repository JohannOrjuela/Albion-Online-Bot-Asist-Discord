from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import Iterator

from .domain import EventStatus, GuildEvent, Signup, SignupResult, SlotDefinition


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
                    event_id, role_key, label, emoji, capacity, position
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                [(event_id, slot.key, slot.label, slot.emoji, slot.capacity, index)
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
                "SELECT * FROM event_slots WHERE event_id = ? ORDER BY position", (event_id,)
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
                SlotDefinition(row["role_key"], row["label"], row["emoji"], row["capacity"])
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
