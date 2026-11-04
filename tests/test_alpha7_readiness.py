"""Alpha 8: all-away mirrors FSM states, manual decisions included."""
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from custom_components.family_presence.bag_schedule import BagSchedule
from custom_components.family_presence.coordinator import PersonSources, ShadowCoordinator
from custom_components.family_presence.fsm import Event, State


class HouseholdAggregationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 3, 7, 30, tzinfo=timezone.utc)
        self.sources = {
            "phone": "not_home", "watch": "off",
            "bag": "off", "old": "away",
        }

        async def instant_sleep(_seconds):
            return None

        self.sleep = instant_sleep

    def create(self, *, bag_schedule=BagSchedule(), people=None):
        return ShadowCoordinator(
            people if people is not None else [
                PersonSources("child", "Child", iphone="phone",
                              watch="watch", bag="bag", reference="old",
                              bag_schedule=bag_schedule)
            ],
            read_state=self.sources.get,
            clock=lambda: self.now,
            sleep=self.sleep,
            local_timezone=ZoneInfo("Europe/Rome"),
        )

    async def test_initial_unknown_is_off(self):
        c = self.create()
        self.assertIs(c.all_away(), False)
        self.assertEqual(c.household_assessment().status, "incomplete")
        self.assertEqual(c.household_assessment().unresolved, ("child",))

    async def test_manual_force_away_immediately_switches_on(self):
        c = self.create()
        await c.force_state("child", State.AWAY)
        self.assertIs(c.all_away(), True)
        a = c.household_assessment()
        self.assertTrue(a.all_away)
        self.assertEqual(a.status, "all_away")
        self.assertEqual(a.reasons["child"], "away_forzato")

    async def test_force_home_immediately_switches_off_and_back(self):
        c = self.create()
        await c.force_state("child", State.AWAY)
        self.assertTrue(c.all_away())
        await c.force_state("child", State.HOME)
        self.assertFalse(c.all_away())
        self.assertEqual(c.household_assessment().status, "presence_indicated")
        self.assertEqual(c.household_assessment().reasons["child"], "home_forzato")
        await c.force_state("child", State.AWAY)
        self.assertTrue(c.all_away())

    async def test_manual_away_is_authoritative_over_live_contradictions(self):
        c = self.create()
        self.sources.update(phone="home", watch="on", bag="on")
        await c.force_state("child", State.AWAY)
        self.assertIs(c.all_away(), True)
        a = c.household_assessment()
        self.assertEqual(a.status, "all_away")
        self.assertIn("iphone_home_con_fsm_away", a.source_warnings["child"])
        self.assertIn("watch_on_con_fsm_away", a.source_warnings["child"])
        self.assertEqual(a.reasons["child"], "away_forzato")

    async def test_restored_away_counts_without_source_reconfirmation(self):
        c = self.create()
        await c.force_state("child", State.AWAY)
        saved = c.snapshot()
        restored = self.create()
        self.assertEqual(restored.restore_snapshot(saved), 1)
        self.assertEqual(restored.state("child"), State.AWAY)
        self.assertTrue(restored.runtime["child"].restored_from_storage)
        self.assertTrue(restored.all_away())
        self.assertEqual(restored.household_assessment().reasons["child"],
                         "away_ripristinato")

    async def test_unavailable_sources_warn_but_do_not_override_away(self):
        c = self.create()
        await c.force_state("child", State.AWAY)
        self.sources.update(phone="unavailable", watch="unknown", bag=None)
        self.assertTrue(c.all_away())
        a = c.household_assessment()
        self.assertIn("iphone_non_disponibile", a.source_warnings["child"])
        self.assertIn("watch_non_disponibile", a.source_warnings["child"])
        self.assertIn("zaino_non_disponibile", a.source_warnings["child"])

    async def test_disabled_bag_does_not_raise_disabled_source_warning(self):
        c = self.create(bag_schedule=BagSchedule(enabled=False))
        await c.force_state("child", State.AWAY)
        self.sources["bag"] = "unavailable"
        self.assertTrue(c.all_away())
        self.assertNotIn("child", c.household_assessment().source_warnings)

    async def test_near_home_or_unknown_prevents_on(self):
        people = [
            PersonSources("a", "A", iphone="phone"),
            PersonSources("b", "B", watch="watch"),
        ]
        c = self.create(people=people)
        await c.force_state("a", State.AWAY)
        self.assertFalse(c.all_away())
        self.assertEqual(c.household_assessment().status, "incomplete")

        c.runtime["b"].state = State.NEAR_HOME
        self.assertFalse(c.all_away())
        self.assertEqual(c.household_assessment().status, "presence_indicated")
        await c.force_state("b", State.AWAY)
        self.assertTrue(c.all_away())
        await c.force_state("a", State.HOME)
        self.assertFalse(c.all_away())

    async def test_four_member_truth_table(self):
        people = [PersonSources(str(i), str(i)) for i in range(4)]
        c = self.create(people=people)
        for key in c.people:
            await c.force_state(key, State.AWAY)
        self.assertTrue(c.all_away())
        for state in (State.HOME, State.NEAR_HOME, None):
            c.runtime["2"].state = state
            self.assertFalse(c.all_away())
        c.runtime["2"].state = State.AWAY
        self.assertTrue(c.all_away())

    async def test_empty_household_cannot_be_called_empty(self):
        c = self.create(people=[])
        self.assertFalse(c.all_away())
        self.assertEqual(c.household_assessment().status, "incomplete")

    async def test_legacy_disagreement_is_diagnostic_only(self):
        c = self.create()
        await c.force_state("child", State.AWAY)
        self.sources["old"] = "home"
        a = c.household_assessment()
        self.assertTrue(a.all_away)
        self.assertEqual(a.divergent, ("child",))

    async def test_new_automatic_event_can_override_manual_force(self):
        c = self.create()
        await c.force_state("child", State.AWAY)
        self.now = self.now.replace(minute=31)
        self.sources["phone"] = "home"
        await c.process("child", Event.IPHONE_ARRIVED, event_time=self.now)
        self.assertFalse(c.all_away())
        self.now = self.now.replace(minute=32)
        self.sources["phone"] = "not_home"
        await c.process("child", Event.IPHONE_LEFT, event_time=self.now)
        self.assertTrue(c.all_away())


if __name__ == "__main__":
    unittest.main()
