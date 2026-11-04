"""HACS RC5 packaging must be self-contained and installable as a flat ZIP."""
import io
import json
from pathlib import Path
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "family_presence"
COMPONENT = ROOT / "custom_components" / DOMAIN


class HacsRC5PackagingTests(unittest.TestCase):
    def test_single_integration_and_metadata_are_consistent(self):
        self.assertEqual([p.name for p in (ROOT / "custom_components").iterdir()
                          if p.is_dir()], [DOMAIN])
        metadata = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(metadata["zip_release"])
        self.assertTrue(metadata["content_in_root"])
        self.assertEqual((ROOT / "brand" / "icon.png").read_bytes(),
                         (COMPONENT / "brand" / "icon.png").read_bytes())
        self.assertEqual(metadata["filename"], "family_presence.zip")
        self.assertTrue(metadata["hide_default_branch"])
        self.assertEqual(manifest["domain"], DOMAIN)
        self.assertEqual(
            json.loads((ROOT / "manifest.json").read_text(encoding="utf-8")),
            manifest,
            "The root manifest must exactly match the shipped integration",
        )
        self.assertEqual(manifest["version"], "0.1.0rc5")

    def test_hacs_update_repository_skips_missing_directory_lookup(self):
        """Model the early HACS integration.py manifest_path decision.

        content_in_root is evaluated BEFORE get_first_directory_in_directory,
        bypassing the former None name and selecting /manifest.json.
        """
        metadata = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        tree = [str(p.relative_to(ROOT)).replace("\\", "/")
                for p in ROOT.rglob("*") if p.is_file()]
        remote_path = "custom_components"
        if metadata.get("content_in_root"):
            remote_path = ""
        elif remote_path == "custom_components":
            subdirs = sorted(p.name for p in (ROOT / "custom_components").iterdir()
                             if p.is_dir())
            remote_path = f"custom_components/{subdirs[0] if subdirs else None}"
        manifest_path = ("manifest.json" if metadata.get("content_in_root")
                         else f"{remote_path}/manifest.json")
        self.assertEqual(manifest_path, "manifest.json")
        self.assertIn(manifest_path, tree)
        self.assertNotIn("None", manifest_path)

    def test_release_zip_extraction_has_flat_manifest_at_destination(self):
        """HACS extracts ZIP directly into /config/custom_components/family_presence."""
        contents = io.BytesIO()
        with ZipFile(contents, "w", ZIP_DEFLATED) as archive:
            for path in sorted(COMPONENT.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, path.relative_to(COMPONENT).as_posix())
        with ZipFile(contents) as archive:
            names = archive.namelist()
            self.assertIn("manifest.json", names)
            self.assertIn("__init__.py", names)
            self.assertIn("config_flow.py", names)
            self.assertNotIn("family_presence/manifest.json", names)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["version"], "0.1.0rc5")


if __name__ == "__main__":
    unittest.main()
