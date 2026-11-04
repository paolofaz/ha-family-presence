"""RC5 device grouping and strict gate unlock input contract."""
import unittest
from custom_components.family_presence.devices import (
    household_device_info,
)
from test_source_adapter import load_source_module


class RC5DeviceAndGateTests(unittest.TestCase):
    def test_one_stable_virtual_device_for_all_family_members(self):
        home = household_device_info("entry")
        same = household_device_info("entry")
        different_entry = household_device_info("other_entry")
        self.assertEqual(home["name"], "Casa")
        self.assertEqual(home["identifiers"], same["identifiers"])
        self.assertNotEqual(home["identifiers"], different_entry["identifiers"])

    def test_gate_physical_event_accepts_lock_unlock_without_false_pulses(self):
        source, _ = load_source_module()
        event = source._gate_opening
        self.assertTrue(event("switch.gate", "off", "on"))
        self.assertTrue(event("binary_sensor.gate", "off", "on"))
        self.assertTrue(event("lock.gate", "locked", "unlocked"))
        self.assertTrue(event("lock.gate", "unlocking", "unlocked"))
        self.assertTrue(event("lock.gate", "locked", "open"))
        for old, new in (
            ("locked", "unlocking"), ("unlocked", "locked"),
            ("unavailable", "unlocked"), ("unlocked", "open"),
        ):
            self.assertFalse(event("lock.gate", old, new))
        self.assertFalse(event("switch.gate", "on", "off"))


if __name__ == "__main__":
    unittest.main()
