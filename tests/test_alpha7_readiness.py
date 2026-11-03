"""Alpha 7: conservative household readiness is informational, not an alarm command."""
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from custom_components.family_presence.bag_schedule import BagSchedule
from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, State


class Alpha7ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 7, 30, tzinfo=timezone.utc)
        self.sources = {
            "phone": "not_home",
            "watch": "off",
            "bag": "off",
            "old": "away",
        }

        async def instant_sleep(_seconds):
            return None

        self.sleep = instant_sleep

    def create(self, *, bag_schedule=BagSchedule(), people=None):
        return ShadowCoordinator(
            people or [PersonSources("child", "Child", iphone="phone",
                                      watch="watch", bag="bag", reference="old",
                                      bag_schedule=bag_schedule)],
            read_state=self.sources.get,
            clock=lambda: self.now,
            sleep=self.sleep,
            local_timezone=ZoneInfo("Europe/Rome"),
        )

    async def test_observed_phone_away_is_only_candidate_not_alarm_permission(self):
        engine = self.create()
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        assessment = engine.household_assessment()
        self.assertEqual(assessment.status, "candidate_empty")
        self.assertEqual(assessment.reasons["child"], "away_osservato_candidato")
        self.assertIs(engine.all_away(), True)

    async def test_manual_away_does_not_authorize_house_empty(self):
        engine = self.create()
        await engine.force_state("child", State.AWAY)
        self.assertEqual(engine.state("child"), State.AWAY)
        a = engine.household_assessment()
        self.assertEqual(a.status, "indeterminate")
        self.assertEqual(a.reasons["child"], "away_manuale_non_verificato")
        self.assertIsNone(engine.all_away())

        # A later genuine source event can establish a fresh observed AWAY.
        self.now = self.now.replace(minute=31)
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.assertEqual(engine.household_assessment().status, "candidate_empty")

    async def test_manual_home_blocks_candidate_empty(self):
        engine = self.create()
        await engine.force_state("child", State.HOME)
        a = engine.household_assessment()
        self.assertEqual(a.status, "presence_indicated")
        self.assertEqual(a.reasons["child"], "home_manuale_indicato")
        self.assertIs(engine.all_away(), False)

    async def test_restored_away_is_indeterminate_until_real_event(self):
        before = self.create()
        await before.process("child", Event.IPHONE_LEFT, event_time=self.now)
        restored = self.create()
        self.assertEqual(restored.restore_snapshot(before.snapshot()), 1)
        self.assertEqual(restored.state("child"), State.AWAY)
        self.assertEqual(restored.household_assessment().status, "indeterminate")
        self.assertEqual(restored.household_assessment().reasons["child"],
                         "stato_ripristinato_non_verificato")

    async def test_phone_at_home_and_watch_on_veto_empty_candidate(self):
        engine = self.create()
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.sources["phone"] = "home"
        self.assertEqual(engine.household_assessment().reasons["child"],
                         "iphone_segnala_casa")
        self.assertIsNone(engine.all_away())

        self.sources["phone"] = "not_home"
        self.sources["watch"] = "on"
        self.assertEqual(engine.household_assessment().reasons["child"],
                         "watch_rilevato_vicino_casa")
        self.assertIsNone(engine.all_away())

    async def test_unavailable_sources_cannot_prove_empty(self):
        engine = self.create()
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.sources.update(phone="unavailable", watch="unknown", bag="unavailable")
        self.assertEqual(engine.household_assessment().status, "indeterminate")
        self.assertEqual(engine.household_assessment().reasons["child"],
                         "fonti_non_disponibili")

    async def test_bag_on_is_not_a_permanent_veto_with_phone_outside(self):
        engine = self.create()
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.sources["bag"] = "on"
        self.assertEqual(engine.household_assessment().status, "candidate_empty")

        # Without a phone outside, a present bag and AWAY state are ambiguous.
        self.sources["phone"] = "unavailable"
        self.assertEqual(engine.household_assessment().reasons["child"],
                         "zaino_presente_senza_conferma_uscita")

    async def test_disabled_bag_is_not_a_reliable_source(self):
        engine = self.create(bag_schedule=BagSchedule(enabled=False))
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.sources.update(phone="unknown", watch="unavailable", bag="off")
        self.assertEqual(engine.household_assessment().reasons["child"],
                         "fonti_non_disponibili")

    async def test_missing_person_and_near_home_block_candidate(self):
        people = [
            PersonSources("a", "A", iphone="phone"),
            PersonSources("b", "B", watch="watch"),
        ]
        engine = self.create(people=people)
        await engine.process("a", Event.IPHONE_LEFT, event_time=self.now)
        a = engine.household_assessment()
        self.assertEqual(a.status, "indeterminate")
        self.assertIn("b", a.unresolved)
        self.assertEqual(a.reasons["b"], "stato_sconosciuto")

        engine.runtime["b"].state = State.NEAR_HOME
        engine.runtime["b"].state_origin = "observed_transition"
        self.assertEqual(engine.household_assessment().status, "presence_indicated")
        self.assertIs(engine.all_away(), False)

    async def test_yaml_mismatch_is_only_a_diagnostic(self):
        engine = self.create()
        await engine.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.sources["old"] = "home"
        a = engine.household_assessment()
        self.assertEqual(a.divergent, ("child",))
        self.assertEqual(a.status, "candidate_empty")
        self.assertEqual(engine.state("child"), State.AWAY)


if __name__ == "__main__":
    unittest.main()
