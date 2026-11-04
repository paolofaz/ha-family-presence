"""RC1: verify unchanged YAML alarm/lock semantics without doing HA writes."""
import itertools
import unittest

from custom_components.family_presence.activation_contract import (
    home_certainly_empty,
    should_arm_away,
    should_disarm,
    should_warn_unlocked_after_delay,
)


class RC1ActivationContractTests(unittest.TestCase):
    def test_four_person_truth_table_including_forced_and_uninitialized(self):
        states = ("home", "near_home", "away", None)
        for combination in itertools.product(states, repeat=4):
            with self.subTest(states=combination):
                self.assertEqual(
                    home_certainly_empty(combination),
                    all(state == "away" for state in combination),
                )
        self.assertFalse(home_certainly_empty(()))
        self.assertTrue(home_certainly_empty(("away",) * 4))

    def test_arm_requires_empty_house_lock_and_disarmed_alarm(self):
        for empty, lock, alarm in itertools.product(
            (False, True),
            (None, "unknown", "unlocked", "locked", "unavailable"),
            (None, "unknown", "unavailable", "disarmed",
             "arming", "armed_away", "armed_home"),
        ):
            with self.subTest(empty=empty, lock=lock, alarm=alarm):
                expected = empty and lock == "locked" and alarm == "disarmed"
                self.assertEqual(
                    should_arm_away(all_away=empty, lock_state=lock, alarm_state=alarm),
                    expected,
                )

    def test_return_home_disarms_only_on_valid_transition(self):
        for before, after, alarm in itertools.product(
            (None, "unknown", "unavailable", "home", "near_home", "away"),
            ("unknown", "unavailable", "home", "near_home", "away"),
            (None, "unavailable", "disarmed", "arming", "armed_away", "armed_home"),
        ):
            expected = (
                before in ("near_home", "away") and after == "home"
                and alarm in ("arming", "armed_away")
            )
            self.assertEqual(
                should_disarm(previous=before, current=after, alarm_state=alarm),
                expected,
            )

    def test_unlocked_warning_does_not_attempt_to_lock(self):
        self.assertFalse(
            should_warn_unlocked_after_delay(all_away=False, lock_state="unlocked")
        )
        self.assertFalse(
            should_warn_unlocked_after_delay(all_away=True, lock_state="locked")
        )
        self.assertTrue(
            should_warn_unlocked_after_delay(all_away=True, lock_state="unlocked")
        )

    def test_manual_away_has_same_aggregate_semantics(self):
        # Provenance (sensor, manual, restored) does not alter this truth table.
        for origin in ("manual_force", "restored", "observed_transition"):
            with self.subTest(origin=origin):
                self.assertTrue(home_certainly_empty(("away", "away", "away", "away")))
                self.assertTrue(should_arm_away(
                    all_away=True, lock_state="locked", alarm_state="disarmed"
                ))
                self.assertFalse(home_certainly_empty(("away", "away", "away", "home")))


if __name__ == "__main__":
    unittest.main()
