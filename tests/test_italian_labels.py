"""Italian labels are presentation-only and cover all current FSM reasons."""
import unittest

from custom_components.family_presence.fsm import (
    BagPolicy, BagStatus, Event, Evidence, State, decide,
)
from custom_components.family_presence.labels import (
    BAG_POLICY_CHOICES_IT, bag_policy_label, reason_label,
)


class ItalianLabelsTests(unittest.TestCase):
    def test_bag_policy_labels_explain_real_behavior(self):
        self.assertEqual(
            BAG_POLICY_CHOICES_IT,
            {
                "always": "Priorità assoluta",
                "legacy": "Fascia scolastica (lun–ven 07:00–09:10)",
            },
        )
        self.assertEqual(bag_policy_label(BagPolicy.ALWAYS), "Priorità assoluta")
        self.assertIn("scolastica", bag_policy_label(BagPolicy.LEGACY))
        self.assertEqual(BagPolicy.ALWAYS.value, "always")  # Config stays compatible.

    def test_every_current_fsm_reason_renders_in_italian(self):
        cases = [
            (State.HOME, Event.IPHONE_LEFT, Evidence()),
            (State.AWAY, Event.IPHONE_ARRIVED, Evidence()),
            (State.HOME, Event.WATCH_LOST, Evidence(iphone_outside=True)),
            (State.HOME, Event.WATCH_LOST, Evidence(gate_exit=True)),
            (State.HOME, Event.WATCH_LOST, Evidence(door_closed_exit=True)),
            (State.HOME, Event.WATCH_LOST, Evidence(lock_exit=True)),
            (State.HOME, Event.WATCH_LOST, Evidence(alarm_armed_away=True)),
            (State.NEAR_HOME, Event.WATCH_LOST, Evidence()),
            (State.AWAY, Event.WATCH_SEEN, Evidence(door_open_entry=True)),
            (State.AWAY, Event.WATCH_SEEN, Evidence(door_unlock_entry=True)),
            (State.AWAY, Event.WATCH_SEEN, Evidence(gate_entry=True)),
            (State.AWAY, Event.WATCH_SEEN, Evidence()),
            (State.NEAR_HOME, Event.PHYSICAL_ENTRY,
             Evidence(watch_detected=True, physical_event_label="gate")),
            (State.NEAR_HOME, Event.PHYSICAL_ENTRY,
             Evidence(watch_detected=True, physical_event_label="door opened")),
            (State.NEAR_HOME, Event.PHYSICAL_ENTRY,
             Evidence(watch_detected=True, physical_event_label="lock unlocked")),
            (State.AWAY, Event.BAG_ARRIVED, Evidence()),
            (State.HOME, Event.BAG_LEFT, Evidence(school_bag_window=True)),
            (State.HOME, Event.RECONCILE, Evidence(bag_status=BagStatus.ABSENT)),
        ]
        for current, event, evidence in cases:
            decision = decide(current, event, evidence)
            self.assertIsNotNone(decision, msg=str((current, event)))
            translated = reason_label(decision.reason)
            with self.subTest(event=event, original=decision.reason):
                self.assertNotEqual(translated, decision.reason)
                self.assertNotIn("Watch detected", translated)
                self.assertNotIn("Bag ", translated)
                self.assertNotIn("iPhone left", translated)
        self.assertIsNone(reason_label(None))

    def test_existing_alpha_reason_is_translated_without_recalculation(self):
        self.assertEqual(
            reason_label("iPhone left home zone"),
            "iPhone uscito dalla zona casa",
        )
        self.assertEqual(
            reason_label("Bag absent (priority)"),
            "Zaino assente: priorità assoluta",
        )


if __name__ == "__main__":
    unittest.main()
