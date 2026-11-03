"""Alpha 9: independent YAML-vs-shadow parity with no control side effects."""
import unittest
from datetime import datetime, timedelta, timezone

from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import State


class LegacyAggregateParityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
        self.raw = {"old_a": "home", "old_b": "home"}
        self.people = [
            PersonSources("a", "Paolo", reference="old_a"),
            PersonSources("b", "Cristina", reference="old_b"),
        ]
        self.engine = self.new()

    def new(self, *, people=None):
        return ShadowCoordinator(
            self.people if people is None else people,
            read_state=self.raw.get,
            clock=lambda: self.now,
        )

    async def set_states(self, a, b):
        await self.engine.force_state("a", a)
        await self.engine.force_state("b", b)

    async def test_aligned_home_states_and_false_aggregate(self):
        await self.set_states(State.HOME, State.HOME)
        cmp = self.engine.legacy_comparison()
        self.assertEqual(cmp.status, "aligned")
        self.assertFalse(cmp.legacy_expected_all_away)
        self.assertFalse(cmp.shadow_all_away)
        self.assertIs(cmp.aggregate_matches_legacy, True)
        self.assertEqual(cmp.differing_members, ())
        self.assertIsNone(self.engine.parity_diverged_since)

    async def test_all_forced_away_is_on_and_matches_yaml(self):
        self.raw.update(old_a="away", old_b="away")
        await self.set_states(State.AWAY, State.AWAY)
        cmp = self.engine.legacy_comparison()
        self.assertTrue(self.engine.all_away())
        self.assertEqual(cmp.status, "aligned")
        self.assertTrue(cmp.legacy_expected_all_away)
        self.assertIs(cmp.aggregate_matches_legacy, True)

    async def test_aggregate_mismatch_has_start_and_resolves(self):
        self.raw.update(old_a="away", old_b="away")
        await self.set_states(State.AWAY, State.HOME)
        cmp = self.engine.legacy_comparison()
        self.assertEqual(cmp.status, "aggregate_divergence")
        self.assertEqual(cmp.differing_members, ("b",))
        self.assertTrue(cmp.legacy_expected_all_away)
        self.assertFalse(cmp.shadow_all_away)
        self.assertEqual(self.engine.parity_diverged_since, self.now)

        self.now += timedelta(seconds=57)
        await self.engine.force_state("b", State.AWAY)
        self.assertEqual(self.engine.legacy_comparison().status, "aligned")
        self.assertIsNone(self.engine.parity_diverged_since)

    async def test_member_swaps_are_reported_even_if_both_aggregates_off(self):
        self.raw.update(old_a="home", old_b="away")
        await self.set_states(State.AWAY, State.HOME)
        cmp = self.engine.legacy_comparison()
        self.assertEqual(cmp.status, "member_divergence")
        self.assertIs(cmp.aggregate_matches_legacy, True)
        self.assertEqual(cmp.differing_members, ("a", "b"))
        self.assertFalse(cmp.legacy_expected_all_away)
        self.assertFalse(cmp.shadow_all_away)

    async def test_reference_changes_refresh_without_modifying_fsm(self):
        await self.set_states(State.HOME, State.HOME)
        self.assertEqual(self.engine.parity_status, "aligned")
        self.now += timedelta(minutes=1)
        self.raw["old_a"] = "away"
        self.engine.notify_source_update("a")
        self.assertEqual(self.engine.parity_status, "member_divergence")
        self.assertEqual(self.engine.parity_diverged_since, self.now)
        self.assertEqual(self.engine.state("a"), State.HOME)

        self.now += timedelta(seconds=25)
        self.raw["old_b"] = "away"
        self.engine.notify_source_update("b")
        self.assertEqual(self.engine.parity_status, "aggregate_divergence")
        self.assertEqual(
            self.engine.parity_diverged_since,
            datetime(2026, 11, 3, 20, 1, tzinfo=timezone.utc),
        )  # uninterrupted disagreement retains original time

        self.now += timedelta(seconds=4)
        self.raw.update(old_a="home", old_b="home")
        self.engine.notify_source_update("a")
        self.assertEqual(self.engine.parity_status, "aligned")
        self.assertIsNone(self.engine.parity_diverged_since)

    async def test_partial_reference_configuration_does_not_invent_truth(self):
        engine = self.new(people=[
            PersonSources("a", "Paolo", reference="old_a"),
            PersonSources("b", "Cristina"),
        ])
        await engine.force_state("a", State.HOME)
        await engine.force_state("b", State.HOME)
        cmp = engine.legacy_comparison()
        self.assertEqual(cmp.status, "not_configured")
        self.assertEqual(cmp.missing_reference_members, ("b",))
        self.assertIsNone(cmp.legacy_expected_all_away)
        self.assertIsNone(cmp.aggregate_matches_legacy)
        self.assertIsNone(engine.parity_diverged_since)

    async def test_unknown_or_unavailable_reference_is_not_treated_as_comparable(self):
        await self.set_states(State.HOME, State.HOME)
        for raw in (None, "unknown", "unavailable", "not_a_state"):
            with self.subTest(raw=raw):
                self.raw["old_b"] = raw
                self.engine.notify_source_update("b")
                cmp = self.engine.legacy_comparison()
                self.assertEqual(cmp.status, "reference_unavailable")
                self.assertEqual(cmp.unavailable_reference_members, ("b",))
                self.assertIsNone(cmp.legacy_expected_all_away)
                self.assertIsNone(self.engine.parity_diverged_since)

    async def test_unknown_shadow_member_is_a_member_divergence(self):
        await self.engine.force_state("a", State.HOME)
        cmp = self.engine.legacy_comparison()
        self.assertEqual(cmp.status, "member_divergence")
        self.assertEqual(cmp.differing_members, ("b",))
        self.assertIs(cmp.aggregate_matches_legacy, True)

    async def test_restore_recalculates_parity_without_seeding_from_yaml(self):
        await self.set_states(State.AWAY, State.AWAY)
        snapshot = self.engine.snapshot()
        new = self.new()
        self.assertEqual(new.restore_snapshot(snapshot), 2)
        self.assertEqual(new.state("a"), State.AWAY)
        self.assertEqual(new.state("b"), State.AWAY)
        self.assertTrue(new.all_away())
        cmp = new.legacy_comparison()
        # Aggregate differs (old helpers HOME, shadow all AWAY).
        self.assertEqual(cmp.status, "aggregate_divergence")
        self.assertFalse(cmp.legacy_expected_all_away)
        self.assertIs(cmp.aggregate_matches_legacy, False)
        self.assertEqual(new.parity_diverged_since, self.now)
        self.assertEqual(self.raw, {"old_a": "home", "old_b": "home"})

    async def test_actual_yaml_binary_reports_matches_and_temporary_lag(self):
        self.raw["binary.casa"] = "off"
        engine = ShadowCoordinator(
            self.people, read_state=self.raw.get, clock=lambda: self.now,
            legacy_aggregate="binary.casa",
        )
        await engine.force_state("a", State.HOME)
        await engine.force_state("b", State.HOME)
        snapshot = engine.legacy_comparison()
        self.assertIs(snapshot.actual_legacy_all_away, False)
        self.assertIs(snapshot.actual_legacy_matches_expected, True)
        self.assertIs(snapshot.actual_legacy_matches_shadow, True)

        self.raw.update(old_a="away", old_b="away")
        await engine.force_state("a", State.AWAY)
        await engine.force_state("b", State.AWAY)
        snapshot = engine.legacy_comparison()
        self.assertTrue(snapshot.legacy_expected_all_away)
        self.assertTrue(snapshot.shadow_all_away)
        self.assertIs(snapshot.actual_legacy_matches_expected, False)
        self.assertIs(snapshot.actual_legacy_matches_shadow, False)

        self.raw["binary.casa"] = "on"
        engine.notify_legacy_aggregate_update()
        snapshot = engine.legacy_comparison()
        self.assertEqual(snapshot.actual_legacy_state, "on")
        self.assertIs(snapshot.actual_legacy_matches_expected, True)
        self.assertIs(snapshot.actual_legacy_matches_shadow, True)
        self.assertEqual(snapshot.status, "aligned")

    async def test_actual_legacy_binary_unavailable_never_claims_match(self):
        self.raw.update(old_a="away", old_b="away", **{"binary.casa": "unknown"})
        engine = ShadowCoordinator(
            self.people, read_state=self.raw.get, clock=lambda: self.now,
            legacy_aggregate="binary.casa",
        )
        await engine.force_state("a", State.AWAY)
        await engine.force_state("b", State.AWAY)
        snapshot = engine.legacy_comparison()
        self.assertIsNone(snapshot.actual_legacy_all_away)
        self.assertIsNone(snapshot.actual_legacy_matches_expected)
        self.assertIsNone(snapshot.actual_legacy_matches_shadow)
        self.assertTrue(snapshot.shadow_all_away)
        self.assertTrue(snapshot.legacy_expected_all_away)

    async def test_optional_binary_does_not_change_fsm_or_missing_refs(self):
        self.raw["binary.casa"] = "on"
        engine = ShadowCoordinator(
            [PersonSources("a", "Paolo", reference="old_a"),
             PersonSources("b", "Cristina")],
            read_state=self.raw.get, clock=lambda: self.now,
            legacy_aggregate="binary.casa",
        )
        await engine.force_state("a", State.AWAY)
        await engine.force_state("b", State.AWAY)
        cmp = engine.legacy_comparison()
        self.assertEqual(cmp.status, "not_configured")
        self.assertIsNone(cmp.legacy_expected_all_away)
        self.assertIs(cmp.actual_legacy_all_away, True)
        self.assertIs(cmp.actual_legacy_matches_shadow, True)
        self.assertIsNone(cmp.actual_legacy_matches_expected)

    async def test_empty_household_never_claims_a_comparison(self):
        empty = self.new(people=[])
        cmp = empty.legacy_comparison()
        self.assertEqual(cmp.status, "reference_unavailable")
        self.assertFalse(cmp.shadow_all_away)
        self.assertIsNone(cmp.legacy_expected_all_away)


if __name__ == "__main__":
    unittest.main()
