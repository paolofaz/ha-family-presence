"""RC1 profile audit without Home Assistant imports."""
import unittest

from custom_components.family_presence.operational import (
    RegisteredOutput, audit_registry, profile_from_options,
)
from custom_components.family_presence.presentation import FINAL, SHADOW


class OperationalTests(unittest.TestCase):
    def test_shadow_is_default_and_invalid_input_fails_closed(self):
        self.assertEqual(profile_from_options({}), SHADOW)
        self.assertEqual(profile_from_options({"output_profile": "invalid"}), SHADOW)
        self.assertEqual(profile_from_options({"output_profile": FINAL}), FINAL)

    def test_audit_uses_registered_not_guessed_entity_ids(self):
        mapping = {
            ("sensor", "ent_alice_shadow"): RegisteredOutput("sensor.custom_name"),
            ("binary_sensor", "ent_all_away_shadow"):
                RegisteredOutput("binary_sensor.shadow_house"),
        }
        audit = audit_registry(
            "ent", (("alice", "Alice"),),
            lambda domain, uid: mapping.get((domain, uid), RegisteredOutput(None)),
            legacy_aggregate="binary_sensor.casa_certamente_vuota",
        )
        self.assertTrue(audit.ready)
        self.assertEqual(audit.aggregate_entity_id, "binary_sensor.shadow_house")
        self.assertEqual(audit.member_entity_ids, (("alice", "sensor.custom_name"),))

    def test_missing_disabled_and_legacy_collision_fail_preflight(self):
        def lookup(domain, _uid):
            return (RegisteredOutput(None) if domain == "sensor"
                    else RegisteredOutput("binary_sensor.old", True))
        audit = audit_registry("ent", (("alice", "Alice"),), lookup,
                               legacy_aggregate="binary_sensor.old")
        self.assertFalse(audit.ready)
        self.assertIn("member_unregistered:alice", audit.blockers)
        self.assertIn("aggregate_disabled", audit.blockers)
        self.assertIn("aggregate_is_legacy_reference", audit.blockers)

    def test_empty_household_fails_preflight(self):
        audit = audit_registry("ent", (), lambda _d, _u: RegisteredOutput(None))
        self.assertFalse(audit.ready)
        self.assertIn("missing_household", audit.blockers)


if __name__ == "__main__":
    unittest.main()
