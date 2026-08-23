from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from content_model import detail_source_paths, load_details_content, validate_content_model  # noqa: E402
from content_editor import _validate_documents  # noqa: E402
from project_paths import DETAILS_CONTENT_PATH, RESUME_CONTENT_PATH, SITE_CONTENT_PATH  # noqa: E402
from portfolio_workflow import sync_shared_fields  # noqa: E402


class ContentArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.site = json.loads(SITE_CONTENT_PATH.read_text(encoding="utf-8"))
        cls.details_manifest = json.loads(DETAILS_CONTENT_PATH.read_text(encoding="utf-8"))
        cls.details = load_details_content()
        cls.resume = json.loads(RESUME_CONTENT_PATH.read_text(encoding="utf-8"))

    def test_sources_are_separate_and_related(self) -> None:
        self.assertNotIn("resume", self.site)
        self.assertEqual(self.details_manifest.get("schema_version"), 1)
        self.assertEqual(len(detail_source_paths()), 12)
        self.assertEqual(validate_content_model(self.site, self.details, self.resume), [])
        self.assertEqual(_validate_documents({"site": self.site, "details": self.details, "resume": self.resume}), [])

    def test_case_studies_have_independent_manifest_files(self) -> None:
        sections = self.details_manifest["portfolio"]["sections"]
        case_studies = next(section for section in sections if section["id"] == "case_studies")
        self.assertEqual(
            case_studies["items"],
            [
                {"id": "formula-ev", "file": "details/portfolio/projects/formula-ev.json"},
                {"id": "heat-exchanger", "file": "details/portfolio/projects/heat-exchanger.json"},
                {"id": "spartan-controls", "file": "details/portfolio/projects/spartan-controls.json"},
            ],
        )
        self.assertEqual(
            [study["id"] for study in self.details["portfolio"]["case_studies"]],
            ["formula-ev", "heat-exchanger", "spartan-controls"],
        )

    def test_independent_resume_override_is_preserved(self) -> None:
        updated, report = sync_shared_fields(self.site, self.resume)
        self.assertEqual(updated["contact"]["email"], self.resume["contact"]["email"])
        self.assertIn("Kept resume override: Email", report)

    def test_changed_safe_site_fact_updates_when_resume_has_not_overridden_it(self) -> None:
        site = json.loads(json.dumps(self.site))
        site["identity"]["name"] = "Updated Name"
        updated, report = sync_shared_fields(site, self.resume)
        self.assertEqual(updated["name"], "Updated Name")
        self.assertIn("Updated: Name", report)


if __name__ == "__main__":
    unittest.main()
