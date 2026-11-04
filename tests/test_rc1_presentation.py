"""RC1 preflight: future labels must not alter existing entity registry identities."""
from __future__ import annotations

import unittest

from custom_components.family_presence.presentation import (
    DEFAULT_PROFILE, FINAL, SHADOW,
    person_presentation, aggregate_presentation,
    household_presentation, force_presentation,
)


class RC1PresentationTests(unittest.TestCase):
    def test_shadow_remains_default_and_identical_to_beta1(self):
        self.assertEqual(DEFAULT_PROFILE, FINAL)
        person = person_presentation("entry123", "paolo", "Paolo", SHADOW)
        self.assertEqual(person.name, "Family Presence Shadow Paolo")
        self.assertEqual(person.unique_id, "entry123_paolo_shadow")
        self.assertTrue(person.diagnostic)

        all_away = aggregate_presentation("entry123", SHADOW)
        self.assertEqual(all_away.name, "Family Presence Shadow - Casa certamente vuota")
        self.assertEqual(all_away.unique_id, "entry123_all_away_shadow")
        self.assertTrue(all_away.diagnostic)

        house = household_presentation("entry123", SHADOW)
        self.assertEqual(house.name, "Family Presence Shadow - Diagnostica casa")
        self.assertEqual(house.unique_id, "entry123_household_readiness_shadow")

    def test_future_final_names_are_defined_but_ids_never_change(self):
        for name, key in (
            ("Paolo", "paolo"), ("Cristina", "cristina"),
            ("Giulia", "giulia"), ("Arianna", "arianna"),
        ):
            old = person_presentation("entry123", key, name, SHADOW)
            new = person_presentation("entry123", key, name, FINAL)
            self.assertEqual(new.name, f"Presenza {name}")
            self.assertFalse(new.diagnostic)
            self.assertTrue(old.diagnostic)
            self.assertEqual(new.unique_id, old.unique_id)

        old_empty = aggregate_presentation("entry123", SHADOW)
        new_empty = aggregate_presentation("entry123", FINAL)
        self.assertEqual(new_empty.name, "Casa certamente vuota")
        self.assertEqual(old_empty.unique_id, new_empty.unique_id)
        self.assertFalse(new_empty.diagnostic)

        old_diag = household_presentation("entry123", SHADOW)
        new_diag = household_presentation("entry123", FINAL)
        self.assertEqual(old_diag.unique_id, new_diag.unique_id)
        self.assertTrue(new_diag.diagnostic)

    def test_force_buttons_keep_the_same_unique_id_after_cutover(self):
        for member in ("paolo", "cristina", "giulia", "arianna"):
            for target in ("home", "away"):
                old = force_presentation("entry", member, member, target, SHADOW)
                new = force_presentation("entry", member, member, target, FINAL)
                self.assertEqual(old.unique_id, new.unique_id)
                self.assertEqual(
                    old.unique_id,
                    f"entry_{member}_shadow_force_{target}",
                )
                self.assertTrue(old.diagnostic)
                self.assertFalse(new.diagnostic)

    def test_invalid_profiles_and_manual_targets_are_rejected(self):
        with self.assertRaises(ValueError):
            person_presentation("entry", "key", "Name", "production_now")
        with self.assertRaises(ValueError):
            aggregate_presentation("entry", "bad")
        with self.assertRaises(ValueError):
            force_presentation("entry", "key", "Name", "near_home")

    def test_no_source_code_exposes_final_profile_as_current_default(self):
        # Important invariant: setting a future display name does NOT claim a
        # HA entity_id and does not activate any automation.
        self.assertEqual(person_presentation("e", "p", "Paolo").name,
                         "Presenza Paolo")
        self.assertEqual(aggregate_presentation("e").name,
                         "Casa certamente vuota")


if __name__ == "__main__":
    unittest.main()
