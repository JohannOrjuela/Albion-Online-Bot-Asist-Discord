from datetime import timezone
import unittest
from zoneinfo import ZoneInfo

from albion_bot.parsing import parse_local_datetime, parse_slots


class ParsingTests(unittest.TestCase):
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

