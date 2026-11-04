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

    def test_bag_departure_requires_active_schedule(self):
        self.assertIsNone(decide(State.HOME, Event.BAG_LEFT))
        e = Evidence(bag_departure_active=True, bag_status=BagStatus.ABSENT)
        self.assertEqual(decide(State.HOME, Event.BAG_LEFT, e).state, State.AWAY)
        self.assertIsNone(decide(State.HOME, Event.BAG_LEFT,
                                 Evidence(bag_departure_active=True, bag_enabled=False)))

    def test_bag_return_requires_prior_bag_departure_and_away_or_near_home(self):
        self.assertIsNone(decide(State.AWAY, Event.BAG_ARRIVED))
        self.assertIsNone(decide(State.NEAR_HOME, Event.BAG_ARRIVED))
        self.assertIsNone(decide(State.HOME, Event.BAG_ARRIVED,
                                 bag_return_eligible=True))
        self.assertIsNone(decide(State.AWAY, Event.BAG_ARRIVED,
                                 Evidence(bag_enabled=False), bag_return_eligible=True))
        for state in (State.AWAY, State.NEAR_HOME):
            self.assertEqual(decide(state, Event.BAG_ARRIVED,
                                    bag_return_eligible=True).state, State.HOME)

    def test_bag_departure_does_not_replace_other_away_reason(self):
        self.assertIsNone(decide(State.AWAY, Event.BAG_LEFT,
                                 Evidence(bag_departure_active=True)))

    def test_absent_bag_does_not_veto_future_phone_or_watch(self):
        e = Evidence(bag_status=BagStatus.ABSENT, gate_entry=True)
        self.assertEqual(decide(State.AWAY, Event.IPHONE_ARRIVED, e).state, State.HOME)
        self.assertEqual(decide(State.AWAY, Event.WATCH_SEEN, e).state, State.HOME)
        self.assertIsNone(decide(State.HOME, Event.RECONCILE, e))

    def test_manual_events_always_set_current_state(self):
        self.assertEqual(decide(State.AWAY, Event.MANUAL_HOME).state, State.HOME)
        self.assertEqual(decide(State.HOME, Event.MANUAL_AWAY).state, State.AWAY)
        self.assertIsNotNone(decide(State.HOME, Event.MANUAL_HOME))

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
