from datetime import timezone
import unittest
from zoneinfo import ZoneInfo

from datetime import datetime, timezone

from albion_bot.parsing import parse_game_time, parse_local_datetime, parse_slots


class ParsingTests(unittest.TestCase):
    def test_parses_game_time_as_today_in_utc(self) -> None:
        now = datetime(2026, 7, 21, 16, 45, tzinfo=timezone.utc)
        result = parse_game_time("18:45", now)
        self.assertEqual(result, datetime(2026, 7, 21, 18, 45, tzinfo=timezone.utc))

    def test_rejects_game_time_with_date(self) -> None:
        with self.assertRaisesRegex(ValueError, "formato `18:45`"):
            parse_game_time("21/07/2026 18:45")

    def test_parses_colombian_datetime_as_utc(self) -> None:
        result = parse_local_datetime("20/07/2026 15:30", ZoneInfo("America/Bogota"))
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.isoformat(), "2026-07-20T20:30:00+00:00")

    def test_parses_custom_slots(self) -> None:
        slots = parse_slots("caller:1, healer:2, dps:6")
        self.assertEqual([slot.key for slot in slots], ["caller", "healer", "dps"])
        self.assertEqual([slot.capacity for slot in slots], [1, 2, 6])

    def test_rejects_duplicate_slots(self) -> None:
        with self.assertRaises(ValueError):
            parse_slots("DPS:2, dps:3")


if __name__ == "__main__":
    unittest.main()
