from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from albion_bot.database import Database
from albion_bot.domain import EventStatus, SignupResult, SlotDefinition


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.db")
        self.database.initialize()
        self.event = self.database.create_event(
            guild_id=1,
            channel_id=2,
            creator_id=3,
            activity="arena",
            title="Arena de prueba",
            description="",
            starts_at=datetime.now(timezone.utc) + timedelta(days=1),
            slots=(
                SlotDefinition("tank", "Tanque", "🛡️", 1),
                SlotDefinition("dps", "DPS", "⚔️", 2),
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_signup_capacity_and_role_change(self) -> None:
        self.assertEqual(self.database.signup(self.event.id, 10, "tank"), SignupResult.JOINED)
        self.assertEqual(self.database.signup(self.event.id, 11, "tank"), SignupResult.FULL)
        self.assertEqual(self.database.signup(self.event.id, 10, "dps"), SignupResult.MOVED)
        self.assertEqual(self.database.signup(self.event.id, 11, "tank"), SignupResult.JOINED)

    def test_user_cannot_join_twice(self) -> None:
        self.database.signup(self.event.id, 10, "dps")
        result = self.database.signup(self.event.id, 10, "dps")
        self.assertEqual(result, SignupResult.ALREADY_JOINED)
        loaded = self.database.get_event(self.event.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.signups), 1)  # type: ignore[union-attr]

    def test_closed_event_rejects_signup(self) -> None:
        self.database.set_event_status(self.event.id, EventStatus.CLOSED)
        result = self.database.signup(self.event.id, 10, "dps")
        self.assertEqual(result, SignupResult.EVENT_CLOSED)


if __name__ == "__main__":
    unittest.main()

