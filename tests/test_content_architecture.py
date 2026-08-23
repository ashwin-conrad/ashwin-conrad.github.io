from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import content_model  # noqa: E402
from content_model import compose_site_content, detail_source_paths, load_details_content, load_resume_content, resolve_fact_references, validate_content_model  # noqa: E402
from project_paths import ASSET_RECORD_PATH, FACTS_CONTENT_PATH, DETAILS_CONTENT_PATH, RESUME_CONTENT_PATH, SITE_CONTENT_PATH  # noqa: E402
from portfolio_workflow import sync_shared_fields  # noqa: E402


class ContentArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.site = json.loads(SITE_CONTENT_PATH.read_text(encoding="utf-8"))
        cls.facts = json.loads(FACTS_CONTENT_PATH.read_text(encoding="utf-8"))
        cls.assets = json.loads(ASSET_RECORD_PATH.read_text(encoding="utf-8"))
        cls.details_manifest = json.loads(DETAILS_CONTENT_PATH.read_text(encoding="utf-8"))
        cls.details = load_details_content()
        cls.resume = load_resume_content()

    def test_sources_are_separate_and_related(self) -> None:
        self.assertNotIn("resume", self.site)
        self.assertEqual(self.details_manifest.get("schema_version"), 1)
        self.assertEqual(len(detail_source_paths()), 18)
        self.assertEqual(validate_content_model(self.site, self.details, self.resume, self.facts), [])

    def test_case_studies_have_independent_manifest_files(self) -> None:
        sections = self.details_manifest["website"]["sections"]
        case_studies = next(section for section in sections if section["id"] == "case_studies")
        self.assertEqual(
            case_studies["items"],
            [
                {"id": "project_1", "file": "details/website/projects/experience_1/project_1.json"},
                {"id": "project_2", "file": "details/website/projects/experience_2/project_2.json"},
                {"id": "project_5", "file": "details/website/projects/experience_3/project_5.json"},
            ],
        )
        self.assertEqual(
            [study["id"] for study in self.details["website"]["case_studies"]],
            ["project_1", "project_2", "project_5"],
        )

    def test_portfolio_collections_have_independent_records(self) -> None:
        sections = self.details_manifest["website"]["sections"]
        for section_id, expected_ids in {
            "experience": ["experience_1", "experience_2", "experience_3"],
            "leadership": ["leadership_1", "leadership_2", "leadership_3"],
            "personal_builds": ["build_1", "build_2", "build_3"],
        }.items():
            section = next(section for section in sections if section["id"] == section_id)
            self.assertEqual([item["id"] for item in section["items"]], expected_ids)
            self.assertTrue(all(item["file"].startswith(f"details/website/{section_id.replace('_', '-')}/") for item in section["items"]))

    def test_projects_are_grouped_under_generic_experience_folders(self) -> None:
        case_studies = next(section for section in self.details_manifest["website"]["sections"] if section["id"] == "case_studies")
        self.assertTrue(all("projects/experience_" in item["file"] for item in case_studies["items"]))
        self.assertTrue(all(item["include"] for item in self.details["website"]["case_studies"]))

    def test_public_case_studies_reject_visible_asset_placeholders(self) -> None:
        details = deepcopy(self.details)
        details["website"]["case_studies"][0]["placeholders"] = ["[ADD DIAGRAM]"]
        errors = validate_content_model(self.site, details, self.resume, self.facts)
        self.assertTrue(any("public placeholders" in error for error in errors))

    def test_excluded_website_record_is_not_composed(self) -> None:
        original_read = content_model.read_json_value

        def read_with_one_excluded(path: Path):
            value = original_read(path)
            if path.name == "experience_3.json":
                value = deepcopy(value)
                value["include"] = False
            return value

        with patch.object(content_model, "read_json_value", side_effect=read_with_one_excluded):
            composed = load_details_content()
        self.assertEqual([item["id"] for item in composed["website"]["experience"]["items"]], ["experience_1", "experience_2"])

    def test_canonical_facts_resolve_into_portfolio_records(self) -> None:
        composed = compose_site_content(self.site, self.details, self.facts)
        experience = composed["website"]["experience"]["items"][0]
        build = composed["website"]["personal_builds"]["items"][0]
        self.assertEqual(experience["role"], "Low Voltage Electronics Lead")
        self.assertEqual(experience["organization"], "Formula EV Racing · University of Alberta")
        self.assertEqual(build["title"], "Knife forging")

    def test_facts_cover_reusable_metadata_and_metrics(self) -> None:
        self.assertEqual(self.facts["education"]["education_1"]["institution"], "University of Alberta")
        self.assertEqual(self.facts["projects"]["project_2"]["metrics"]["heat_exchanger_count"], "12+")
        self.assertEqual(self.facts["projects"]["project_3"]["metrics"]["inspection_scope_count"], "500+")
        self.assertEqual(self.facts["projects"]["project_5"]["metrics"]["panel_count"], "30+")
        self.assertIn("Python", self.facts["skills"]["data_automation"])
        self.assertEqual(self.facts["recognitions"]["recognition_1"]["dates"], "2024-2025")

    def test_asset_records_supply_image_descriptions_and_display_controls(self) -> None:
        asset = self.assets["images"]["image_01"]
        self.assertEqual(asset["alt"], "Formula EV low-voltage enclosure held at competition")
        self.assertEqual(asset["title"], "Low-voltage hardware")
        self.assertTrue(all(isinstance(value, bool) for value in asset["display"].values()))
        composed = compose_site_content(self.site, self.details, self.facts, self.assets)
        image = composed["website"]["documentation"]["items"][1]
        self.assertEqual(image["alt"], asset["alt"])
        self.assertEqual(image["title"], asset["title"])

    def test_website_and_resume_load_grouped_skill_facts(self) -> None:
        website_skills = self.details["website"]["skills"]["groups"]
        self.assertEqual(website_skills[0]["items"], {"$source": "facts.skills.mechanical_design"})
        from content_model import resolve_fact_references

        resolved = resolve_fact_references(self.details["website"]["skills"], self.facts)
        self.assertIn("Python", resolved["groups"][3]["items"])

    def test_resume_recognition_loads_facts(self) -> None:
        recognition = next(block for block in self.resume["pages"][0]["blocks"] if block.get("heading") == "Recognition")
        resolved = resolve_fact_references(recognition, self.facts)
        self.assertEqual(resolved["items"][0]["role"], "Undergraduate Student Leadership Award")
        self.assertEqual(resolved["items"][0]["dates"], "2024-2025")

    def test_resume_identity_fields_follow_facts_references(self) -> None:
        updated, report = sync_shared_fields(self.site, self.resume, self.facts)
        self.assertEqual(updated["contact"]["email"], {"$source": "facts.identity.email"})
        self.assertIn("Current: Email", report)

    def test_changed_safe_site_fact_updates_when_resume_has_not_overridden_it(self) -> None:
        facts = json.loads(json.dumps(self.facts))
        facts["identity"]["name"] = "Updated Name"
        updated, report = sync_shared_fields(self.site, self.resume, facts)
        self.assertEqual(updated["name"], {"$source": "facts.identity.name"})
        self.assertIn("Current: Name", report)


if __name__ == "__main__":
    unittest.main()
