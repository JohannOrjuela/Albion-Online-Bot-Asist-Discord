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

    def test_build_can_be_assigned_to_template(self) -> None:
        build = self.database.save_build(
            guild_id=1, name="Dawnsong Arena", activity="Arena", weapon="Dawnsong",
            offhand="", head="Royal Cowl", chest="Feyscale Robe", shoes="Cleric Sandals",
            cape="Lymhurst Cape", food="Pork Omelette", potion="Resistance Potion",
            abilities="Q1, W2, E", minimum_ip=1200, notes="Prueba",
        )
        self.database.create_template(1, "Cristal", "arena", "Composición de prueba")
        template = self.database.upsert_template_slot(
            guild_id=1, template_name="Cristal", role_key="dawnsong", label="Dawnsong",
            emoji="🔥", capacity=1, build_id=build.id,
        )
        self.assertIsNotNone(template)
        self.assertEqual(template.slots[0].build_name, "Dawnsong Arena")  # type: ignore[union-attr]

    def test_custom_role_emoji_is_persisted(self) -> None:
        self.database.set_role_emoji(1, "healer", "<:holy:123456789012345678>")
        self.assertEqual(
            self.database.get_role_emojis(1)["healer"],
            "<:holy:123456789012345678>",
        )


if __name__ == "__main__":
    unittest.main()
