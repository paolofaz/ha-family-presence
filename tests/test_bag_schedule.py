"""Configurable per-person backpack departure window."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.family_presence.bag_schedule import (
    ALL_DAYS, SCHOOL_DAYS, BagSchedule, legacy_schedule,
)


class BagScheduleTests(unittest.TestCase):
    def ts(self, year, month, day, hour, minute=0):
        return datetime(year, month, day, hour, minute,
                        tzinfo=ZoneInfo("Europe/Rome"))

    def test_default_school_window(self):
        s = BagSchedule()
        self.assertEqual(s.days, SCHOOL_DAYS)
        self.assertFalse(s.includes(self.ts(2026, 11, 2, 6, 59)))
        self.assertTrue(s.includes(self.ts(2026, 11, 2, 7, 0)))
        self.assertTrue(s.includes(self.ts(2026, 11, 2, 9, 9)))
        self.assertFalse(s.includes(self.ts(2026, 11, 2, 9, 10)))
        self.assertFalse(s.includes(self.ts(2026, 11, 1, 8)))

    def test_full_day_zero_to_zero_including_midnight(self):
        s = BagSchedule(True, "00:00", "00:00", ALL_DAYS)
        for hour in (0, 5, 12, 23):
            self.assertTrue(s.includes(self.ts(2026, 11, 1, hour)))
        self.assertTrue(s.includes(self.ts(2026, 11, 2, 0)))

    def test_disabled_ignores_any_time(self):
        s = BagSchedule(False, "00:00", "00:00", ALL_DAYS)
        self.assertFalse(s.includes(self.ts(2026, 11, 2, 8)))
        self.assertFalse(s.includes(self.ts(2026, 11, 2, 23)))

    def test_overnight_window_uses_previous_day_early_morning(self):
        s = BagSchedule(True, "22:00", "02:00", (0,))
        self.assertTrue(s.includes(self.ts(2026, 11, 2, 23)))
        self.assertTrue(s.includes(self.ts(2026, 11, 3, 1)))
        self.assertFalse(s.includes(self.ts(2026, 11, 3, 3)))
        self.assertFalse(s.includes(self.ts(2026, 11, 4, 1)))

    def test_round_trip_and_bad_configuration(self):
        s = BagSchedule(True, "08:35", "11:15", (0, 2, 4))
        self.assertEqual(BagSchedule.from_dict(s.to_dict()), s)
        for v in ("24:00", "garbage"):
            with self.assertRaises(ValueError):
                BagSchedule(True, v, "12:00", ALL_DAYS)
        with self.assertRaises(ValueError):
            BagSchedule(True, "00:00", "00:00", (7,))

    def test_prior_legacy_configuration_is_just_migration(self):
        self.assertEqual(legacy_schedule("always"),
                         BagSchedule(True, "00:00", "00:00", ALL_DAYS))
        self.assertEqual(legacy_schedule("legacy"), BagSchedule())


if __name__ == "__main__":
    unittest.main()
