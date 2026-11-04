"""Manifest contract for HACS alpha releases."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "family_presence" / "manifest.json"


class ManifestTests(unittest.TestCase):
    def test_shadow_is_visible_as_normal_integration_not_helper(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], "family_presence")
        self.assertEqual(manifest["integration_type"], "hub")
        self.assertTrue(manifest["config_flow"])
        self.assertTrue(manifest["single_config_entry"])

    def test_release_manifest_version_matches_v1(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
