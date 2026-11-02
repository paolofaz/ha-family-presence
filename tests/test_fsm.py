"""Baseline FSM tests; no Home Assistant installation is required."""
import unittest
from datetime import datetime, timezone
from custom_components.family_presence.fsm import (
    BagPolicy, BagStatus, Decision, Event, Evidence, State, decide, recent_before, school_bag_window,
)


class TestPresenceFSM(unittest.TestCase):
    def test_phone(self):
        self.assertEqual(decide(State.HOME, Event.IPHONE_LEFT).state, State.AWAY)
        self.assertEqual(decide(State.AWAY, Event.IPHONE_ARRIVED).state, State.HOME)
        self.assertIsNone(decide(State.AWAY, Event.IPHONE_LEFT))

    def test_watch_on(self):
        self.assertEqual(decide(State.AWAY, Event.WATCH_SEEN).state, State.NEAR_HOME)
        self.assertEqual(decide(State.AWAY, Event.WATCH_SEEN, Evidence(door_open_entry=True)).state, State.HOME)
        self.assertIsNone(decide(State.HOME, Event.WATCH_SEEN))

    def test_watch_off_needs_evidence_when_home(self):
        self.assertIsNone(decide(State.HOME, Event.WATCH_LOST))
        self.assertEqual(decide(State.HOME, Event.WATCH_LOST, Evidence(lock_exit=True)).state, State.AWAY)
        self.assertEqual(decide(State.NEAR_HOME, Event.WATCH_LOST).state, State.AWAY)

    def test_priorities(self):
        e = Evidence(iphone_outside=True, gate_exit=True, alarm_armed_away=True)
        self.assertEqual(decide(State.HOME, Event.WATCH_LOST, e).reason, "iPhone outside")
        e = Evidence(door_open_entry=True, door_unlock_entry=True, gate_entry=True)
        self.assertEqual(decide(State.AWAY, Event.WATCH_SEEN, e), Decision(State.HOME, "Watch detected + recent door opening"))

    def test_physical_entry(self):
        self.assertIsNone(decide(State.NEAR_HOME, Event.PHYSICAL_ENTRY))
        self.assertEqual(decide(State.NEAR_HOME, Event.PHYSICAL_ENTRY, Evidence(watch_detected=True)).state, State.HOME)

    def test_bags_preserve_existing_semantics(self):
        self.assertEqual(decide(State.AWAY, Event.BAG_ARRIVED).state, State.HOME)
        self.assertIsNotNone(decide(State.HOME, Event.BAG_ARRIVED))
        self.assertIsNone(decide(State.HOME, Event.BAG_LEFT))
        self.assertEqual(decide(State.HOME, Event.BAG_LEFT, Evidence(school_bag_window=True)).state, State.AWAY)

    def test_bag_off_wins_over_watch_gate_and_door(self):
        evidence = Evidence(bag_status=BagStatus.ABSENT, gate_entry=True, door_open_entry=True)
        self.assertIsNone(decide(State.AWAY, Event.WATCH_SEEN, evidence))
        self.assertEqual(decide(State.NEAR_HOME, Event.PHYSICAL_ENTRY, evidence).state, State.AWAY)

    def test_bag_off_wins_over_iphone_and_restart(self):
        evidence = Evidence(bag_status=BagStatus.ABSENT)
        self.assertIsNone(decide(State.AWAY, Event.IPHONE_ARRIVED, evidence))
        self.assertEqual(decide(State.HOME, Event.IPHONE_ARRIVED, evidence),
                         Decision(State.AWAY, "Bag absent (priority)"))
        self.assertEqual(decide(State.HOME, Event.RECONCILE, evidence).state, State.AWAY)

    def test_bag_off_all_day_and_arrival_releases_veto(self):
        absent = Evidence(bag_status=BagStatus.ABSENT, school_bag_window=False)
        self.assertEqual(decide(State.HOME, Event.BAG_LEFT, absent).state, State.AWAY)
        self.assertEqual(decide(State.AWAY, Event.BAG_ARRIVED, absent), None)
        self.assertEqual(decide(State.AWAY, Event.BAG_ARRIVED,
                                Evidence(bag_status=BagStatus.PRESENT)).state, State.HOME)

    def test_bag_unknown_and_not_configured_never_veto(self):
        for status in [BagStatus.UNKNOWN, BagStatus.NOT_CONFIGURED]:
            with self.subTest(status=status):
                evidence = Evidence(bag_status=status, door_open_entry=True)
                self.assertEqual(decide(State.AWAY, Event.WATCH_SEEN, evidence).state, State.HOME)

    def test_legacy_policy_preserves_old_false_arrival(self):
        absent = Evidence(bag_status=BagStatus.ABSENT, gate_entry=True)
        self.assertEqual(decide(State.AWAY, Event.WATCH_SEEN, absent,
                                bag_policy=BagPolicy.LEGACY).state, State.HOME)
        self.assertIsNone(decide(State.HOME, Event.BAG_LEFT, absent,
                                 bag_policy=BagPolicy.LEGACY))
        self.assertEqual(decide(State.HOME, Event.BAG_LEFT,
                                Evidence(bag_status=BagStatus.ABSENT, school_bag_window=True),
                                bag_policy=BagPolicy.LEGACY).state, State.AWAY)

    def test_windows(self):
        end = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(recent_before(end, datetime(2026, 11, 2, 11, 58, tzinfo=timezone.utc), 120))
        self.assertFalse(recent_before(end, datetime(2026, 11, 2, 12, 0, 1, tzinfo=timezone.utc), 120))
        self.assertFalse(recent_before(end, None, 120))
        self.assertTrue(school_bag_window(datetime(2026, 11, 2, 7, 0)))
        self.assertFalse(school_bag_window(datetime(2026, 11, 2, 9, 10)))
        self.assertFalse(school_bag_window(datetime(2026, 11, 1, 8, 0)))


if __name__ == "__main__":
    unittest.main()
