from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from project_paths import RESUME_CONTENT_PATH, RESUME_DOCX_OUTPUT_PATH, RESUME_OUTPUT_PATH  # noqa: E402
from resume.build import build_resume  # noqa: E402
from resume.mapper import build_resume_record  # noqa: E402
from resume.validation import (  # noqa: E402
    TemplateValidationError,
    validate_pdf_page_count,
    validate_record,
    validate_resume_document,
    validate_tag_inventory,
)
from resume.word_renderer import (  # noqa: E402
    ContentControlNotFoundError,
    NS,
    control_text,
    fix_page_two_project_layout,
    find_control_by_tag,
    read_content_control_values,
    read_document_root,
    render_word_template,
)
from resume.word_sync import sync_word_values_into_resume  # noqa: E402


class ResumePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resume_data = json.loads(RESUME_CONTENT_PATH.read_text(encoding="utf-8"))
        cls.output_dir = ROOT / "tmp" / "resume-pipeline-tests"
        cls.output_dir.mkdir(parents=True, exist_ok=True)

    def document_hash(self) -> str:
        return hashlib.sha256(RESUME_DOCX_OUTPUT_PATH.read_bytes()).hexdigest()

    def test_editable_document_loading_and_structure(self) -> None:
        validate_resume_document(RESUME_DOCX_OUTPUT_PATH)

    def test_known_content_control_lookup(self) -> None:
        control = find_control_by_tag(RESUME_DOCX_OUTPUT_PATH, "EXP1_COMPANY")
        self.assertEqual(control.tag, "EXP1_COMPANY")
        self.assertEqual(control_text(control.element), "AltaGas - Calgary, AB")

    def test_replacement_keeps_content_control(self) -> None:
        output_path = self.output_dir / "replacement.docx"
        render_word_template(RESUME_DOCX_OUTPUT_PATH, output_path, {"CONTACT_NAME": "Test Resume Name"})
        control = find_control_by_tag(output_path, "CONTACT_NAME")
        self.assertEqual(control_text(control.element), "Test Resume Name")
        with zipfile.ZipFile(output_path) as package:
            self.assertIn(b"<w:sdt", package.read("word/document.xml"))

    def test_field_mapping_targets_expected_tags(self) -> None:
        record = build_resume_record(self.resume_data)
        self.assertEqual(record.values["EXP1_COMPANY"], "AltaGas - Calgary, AB")
        self.assertEqual(record.values["PROJECT3_TITLE"], "Formula EV Electrical Systems")
        self.assertEqual(record.values["COMMUNITY1_TITLE"], "CYDC Basketball Coach")
        validate_record(record)

    def test_missing_control_is_descriptive(self) -> None:
        with self.assertRaisesRegex(ContentControlNotFoundError, "Missing Content Control tag: NOT_A_TEMPLATE_TAG"):
            find_control_by_tag(RESUME_DOCX_OUTPUT_PATH, "NOT_A_TEMPLATE_TAG")

    def test_duplicate_control_is_reported(self) -> None:
        with self.assertRaisesRegex(TemplateValidationError, "Duplicate Content Control tag: CONTACT_NAME"):
            validate_tag_inventory(["CONTACT_NAME", "CONTACT_NAME"], {"CONTACT_NAME"})

    def test_optional_blank_fields_render(self) -> None:
        record = build_resume_record(self.resume_data)
        self.assertEqual(record.values["COMMUNITY2_TITLE"], "")
        output_path = self.output_dir / "blank-optional.docx"
        render_word_template(RESUME_DOCX_OUTPUT_PATH, output_path, record.values)
        self.assertTrue(output_path.exists())

    def test_editable_document_is_unchanged_when_rendering_a_copy(self) -> None:
        before = self.document_hash()
        render_word_template(RESUME_DOCX_OUTPUT_PATH, self.output_dir / "immutability.docx", {"CONTACT_NAME": "Immutable"})
        self.assertEqual(self.document_hash(), before)

    def test_generated_docx_builds_in_place(self) -> None:
        output_path = self.output_dir / "generated-resume.docx"
        shutil.copy2(RESUME_DOCX_OUTPUT_PATH, output_path)
        result = build_resume(self.resume_data, docx_path=output_path, pdf_path=None)
        self.assertEqual(result.docx_path, output_path)
        self.assertTrue(output_path.exists())
        validate_resume_document(output_path)

    def test_page_two_project_table_stays_within_the_page_width(self) -> None:
        output_path = self.output_dir / "page-two-layout.docx"
        shutil.copy2(RESUME_DOCX_OUTPUT_PATH, output_path)
        fix_page_two_project_layout(output_path)
        root = read_document_root(output_path)
        table = next(
            table
            for table in root.xpath("./w:body/w:tbl", namespaces=NS)
            if "SELECTED PROJECT PORTFOLIO" in "".join(table.xpath(".//w:t/text()", namespaces=NS))
        )
        self.assertEqual(table.xpath("./w:tblPr/w:tblW/@w:w", namespaces=NS), ["10656"])
        self.assertEqual(table.xpath("./w:tblPr/w:tblInd/@w:w", namespaces=NS), ["0"])
        self.assertEqual(table.xpath("./w:tblGrid/w:gridCol/@w:w", namespaces=NS), ["5000", "3300", "2356"])

    def test_word_sync_updates_a_copy_of_the_resume_model(self) -> None:
        values = read_content_control_values(RESUME_DOCX_OUTPUT_PATH)
        values.update({"CONTACT_NAME": "Word Edited Name", "GENERAL_SKILL_1": "Word Skill"})
        updated = sync_word_values_into_resume(self.resume_data, values)
        self.assertEqual(updated["name"], "Word Edited Name")
        self.assertEqual(updated["general_skills"][0], "Word Skill")
        self.assertNotEqual(updated, self.resume_data)
        self.assertEqual(self.resume_data["name"], "Ashwin Conrad")

    def test_website_renderer_still_loads(self) -> None:
        from portfolio_workflow import load_content
        from site_renderer import render_engineering_index

        self.assertIn("<html", render_engineering_index(load_content()).lower())

    def test_generated_pdf_has_two_pages_when_available(self) -> None:
        if not RESUME_DOCX_OUTPUT_PATH.exists() or not RESUME_OUTPUT_PATH.exists():
            self.skipTest("Public resume artifacts have not been generated")
        validate_pdf_page_count(RESUME_OUTPUT_PATH)


if __name__ == "__main__":
    unittest.main()
