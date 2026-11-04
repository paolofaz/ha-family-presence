"""RC5 device grouping and strict gate unlock input contract."""
import unittest
from custom_components.family_presence.devices import (
    household_device_info, member_device_info,
)
from test_source_adapter import load_source_module


class RC5DeviceAndGateTests(unittest.TestCase):
    def test_person_devices_have_stable_distinct_identifiers(self):
        paolo = member_device_info("entry", "id-paolo", "Paolo")
        same = member_device_info("entry", "id-paolo", "Paolo Updated")
        cristina = member_device_info("entry", "id-cristina", "Cristina")
        household = household_device_info("entry")
        self.assertEqual(paolo["identifiers"], same["identifiers"])
        self.assertNotEqual(paolo["identifiers"], cristina["identifiers"])
        self.assertNotEqual(paolo["identifiers"], household["identifiers"])

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
