from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectMetadataTests(unittest.TestCase):
    def test_pyproject_exposes_public_project_metadata(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["name"], "ticket-system")
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], [])
        self.assertEqual(project["license"], {"file": "LICENSE"})
        self.assertEqual(project["authors"], [{"name": "Meow-saucee"}])
        self.assertEqual(project["urls"]["Repository"], "https://github.com/Meow-saucee/intelligent-ticket-system")
        self.assertEqual(project["scripts"]["ticket-system"], "ticket_system.cli:main")

    def test_license_and_line_ending_policy_exist(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Meow-saucee", license_text)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* text=auto eol=lf", attributes)
        self.assertIn("*.sh text eol=lf", attributes)


if __name__ == "__main__":
    unittest.main()
