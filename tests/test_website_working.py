from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from project_paths import ASSET_RECORD_PATH, FACTS_CONTENT_PATH, WEBSITE_WORKING_DOCX_PATH  # noqa: E402
from resume.word_renderer import read_content_control_values  # noqa: E402
from website_working import (  # noqa: E402
    collect_website_fields,
    create_working_website,
    project_website_updates,
    validate_website_working_document,
)


class WebsiteWorkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fields = collect_website_fields()

    def test_inventory_covers_direct_copy_and_referenced_sources(self) -> None:
        self.assertGreater(len(self.fields), 250)
        locators = {(field.source_path, field.json_path) for field in self.fields}
        self.assertIn((FACTS_CONTENT_PATH, ("experiences", "experience_1", "role")), locators)
        self.assertIn((ASSET_RECORD_PATH, ("images", "image_01", "alt")), locators)
        self.assertTrue(any(field.json_path == ("title",) and field.group == "00 / Hero" for field in self.fields))
        self.assertFalse(any(field.json_path[-1:] == ("src",) for field in self.fields))
        self.assertFalse(any(field.json_path[-1:] == ("href",) for field in self.fields))

    def test_tags_are_unique_and_stable(self) -> None:
        tags = [field.tag for field in self.fields]
        self.assertEqual(len(tags), len(set(tags)))
        self.assertEqual(tags, [field.tag for field in collect_website_fields()])

    def test_checked_in_working_document_matches_current_sources(self) -> None:
        validate_website_working_document(WEBSITE_WORKING_DOCX_PATH)
        values = read_content_control_values(WEBSITE_WORKING_DOCX_PATH)
        hero_title = next(field for field in self.fields if field.group == "00 / Hero" and field.json_path == ("title",))
        self.assertEqual(values[hero_title.tag], hero_title.value)

    def test_projected_edits_target_the_owner_without_flattening_references(self) -> None:
        values = {field.tag: field.value for field in self.fields}
        fact_field = next(
            field
            for field in self.fields
            if field.source_path == FACTS_CONTENT_PATH
            and field.json_path == ("experiences", "experience_1", "role")
        )
        values[fact_field.tag] = "Word Edited Canonical Role"
        updates = {update.path: update.value for update in project_website_updates(values)}
        self.assertEqual(
            updates[FACTS_CONTENT_PATH]["experiences"]["experience_1"]["role"],
            "Word Edited Canonical Role",
        )

    def test_new_working_website_contains_all_controls(self) -> None:
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "website-working.docx"
            create_working_website(output)
            values = read_content_control_values(output)
        self.assertEqual({field.tag for field in self.fields}, set(values))


if __name__ == "__main__":
    unittest.main()
