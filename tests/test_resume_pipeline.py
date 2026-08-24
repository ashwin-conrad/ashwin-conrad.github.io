from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import zipfile

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from content_model import load_resume_content, resolve_fact_references  # noqa: E402
from design_tokens import load_design_tokens  # noqa: E402
from project_paths import DESIGN_TOKENS_PATH, FACTS_CONTENT_PATH, RESUME_CONTENT_PATH, RESUME_DOCX_OUTPUT_PATH, RESUME_OUTPUT_PATH, RESUME_WORKING_DOCX_PATH  # noqa: E402
import resume.build as resume_build  # noqa: E402
from resume.build import build_resume  # noqa: E402
from resume.mapper import build_resume_record, education_slot_order, word_slot_order  # noqa: E402
from resume.template_builder import create_resume_template  # noqa: E402
from resume.validation import (  # noqa: E402
    TemplateValidationError,
    validate_pdf_page_count,
    validate_record,
    validate_resume_document,
    validate_resume_template_capacity,
    validate_tag_inventory,
)
from resume.word_renderer import (  # noqa: E402
    ContentControlNotFoundError,
    NS,
    control_text,
    find_control_by_tag,
    read_content_control_values,
    render_word_template,
)
from resume.word_sync import sync_word_values_into_resume  # noqa: E402
from resume.theme import STATIC_RESUME_TEXT_STYLES, apply_resume_theme, resume_text_style_for_tag  # noqa: E402


class ResumePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        facts = json.loads(FACTS_CONTENT_PATH.read_text(encoding="utf-8"))
        cls.resume_data = resolve_fact_references(load_resume_content(), facts)
        cls.output_dir = ROOT / "tmp" / "resume-pipeline-tests"
        cls.output_dir.mkdir(parents=True, exist_ok=True)

    def document_hash(self) -> str:
        return hashlib.sha256(RESUME_DOCX_OUTPUT_PATH.read_bytes()).hexdigest()

    def test_editable_document_loading_and_structure(self) -> None:
        validate_resume_document(RESUME_WORKING_DOCX_PATH)

    def test_resume_manifest_composes_section_files(self) -> None:
        composed = load_resume_content()
        headings = [block["heading"] for block in composed["pages"][0]["blocks"]]
        self.assertEqual(
            headings,
            [
                "Education",
                "Technical Skills",
                "Experience",
                "Leadership",
                "Community Involvement",
                "Recognition",
                "Project Portfolio",
            ],
        )

    def test_experience_and_grouped_projects_have_expected_populated_bullets(self) -> None:
        values = read_content_control_values(RESUME_DOCX_OUTPUT_PATH)
        for slot in range(1, 3):
            for bullet in range(1, 5):
                self.assertTrue(values[f"EXP{slot}_BULLET{bullet}"].strip())
        for slot in range(1, 8):
            for bullet in range(1, 3):
                self.assertTrue(values[f"PROJECT{slot}_BULLET{bullet}"].strip())

    def test_known_content_control_lookup(self) -> None:
        control = find_control_by_tag(RESUME_DOCX_OUTPUT_PATH, "EXP1_TITLE")
        self.assertEqual(control.tag, "EXP1_TITLE")
        self.assertEqual(control_text(control.element), "Integrity & Reliability Engineering Student")

    def test_replacement_keeps_content_control(self) -> None:
        output_path = self.output_dir / "replacement.docx"
        render_word_template(RESUME_DOCX_OUTPUT_PATH, output_path, {"CONTACT_NAME": "Test Resume Name"})
        control = find_control_by_tag(output_path, "CONTACT_NAME")
        self.assertEqual(control_text(control.element), "Test Resume Name")
        with zipfile.ZipFile(output_path) as package:
            self.assertIn(b"<w:sdt", package.read("word/document.xml"))

    def test_field_mapping_targets_expected_tags(self) -> None:
        record = build_resume_record(self.resume_data)
        self.assertNotIn("EDU_BULLET1", record.values)
        self.assertEqual(record.values["EDU2_INSTITUTION"], "West Island College")
        self.assertEqual(record.values["EDU2_DEGREE"], "High School - Calgary")
        self.assertEqual(record.values["EDU2_DATES"], "2020-2023")
        self.assertIn("Diversity Equity and Inclusion Club", record.values["EDU2_BULLET2"])
        self.assertEqual(record.values["EXP1_META"], "AltaGas - Calgary, AB")
        self.assertEqual(record.values["LEAD1_TITLE"], "Low Voltage Electronics Lead")
        self.assertEqual(record.values["PROJECT3_TITLE"], "ENG 160 Mechanical Design Project")
        self.assertEqual(record.values["PROJECT1_CATEGORY"], "Industry Projects")
        self.assertEqual(record.values["PROJECT2_CATEGORY"], "")
        self.assertEqual(record.values["PROJECT3_CATEGORY"], "Course Projects")
        self.assertEqual(record.values["PROJECT5_CATEGORY"], "Extracurricular Projects")
        self.assertEqual(record.values["PROJECT6_CATEGORY"], "Personal Projects")
        self.assertEqual(record.values["COMM1_TITLE"], "Youth Basketball Coach")
        validate_record(record)

    def test_word_slot_order_is_content_configured_with_generic_ids(self) -> None:
        self.assertEqual(education_slot_order(self.resume_data), ("education_1", "education_2"))
        experiences, leadership, community, recognition, projects = word_slot_order(self.resume_data)
        self.assertEqual(experiences, ("experience_2", "experience_3"))
        self.assertEqual(leadership, ("leadership_2", "leadership_1"))
        self.assertEqual(community, ("community_1",))
        self.assertEqual(recognition, ("recognition_1", "recognition_2", "recognition_3"))
        self.assertEqual(
            projects,
            ("project_2", "project_3", "project_9", "project_10", "project_1", "project_6", "project_7"),
        )

    def test_missing_control_is_descriptive(self) -> None:
        with self.assertRaisesRegex(ContentControlNotFoundError, "Missing Content Control tag: NOT_A_TEMPLATE_TAG"):
            find_control_by_tag(RESUME_DOCX_OUTPUT_PATH, "NOT_A_TEMPLATE_TAG")

    def test_duplicate_control_is_reported(self) -> None:
        with self.assertRaisesRegex(TemplateValidationError, "Duplicate Content Control tag: CONTACT_NAME"):
            validate_tag_inventory(["CONTACT_NAME", "CONTACT_NAME"], {"CONTACT_NAME"})

    def test_blank_surplus_bullet_capacity_survives_post_sync_validation(self) -> None:
        blank_path = self.output_dir / "blank-surplus-bullet.docx"
        populated_path = self.output_dir / "populated-surplus-bullet.docx"
        create_resume_template(blank_path)
        render_word_template(blank_path, blank_path, {"EDU_BULLET2": ""})
        values = read_content_control_values(blank_path)
        allowed_tags = set(values) - {"EDU_BULLET2"}

        actual_tags = validate_resume_template_capacity(
            blank_path,
            required_tags=allowed_tags,
            allowed_tags=allowed_tags,
        )
        self.assertIn("EDU_BULLET2", actual_tags)

        render_word_template(blank_path, populated_path, {"EDU_BULLET2": "Unexpected data"})
        with self.assertRaisesRegex(TemplateValidationError, "Unexpected Content Control tag: EDU_BULLET2"):
            validate_resume_template_capacity(
                populated_path,
                required_tags=allowed_tags,
                allowed_tags=allowed_tags,
            )

    def test_optional_blank_fields_render(self) -> None:
        record = build_resume_record(self.resume_data)
        self.assertEqual(record.values["RECOG1_META"], "")
        output_path = self.output_dir / "blank-optional.docx"
        render_word_template(RESUME_WORKING_DOCX_PATH, output_path, record.values)
        self.assertTrue(output_path.exists())

    def test_editable_document_is_unchanged_when_rendering_a_copy(self) -> None:
        before = hashlib.sha256(RESUME_WORKING_DOCX_PATH.read_bytes()).hexdigest()
        render_word_template(RESUME_WORKING_DOCX_PATH, self.output_dir / "immutability.docx", {"CONTACT_NAME": "Immutable"})
        self.assertEqual(hashlib.sha256(RESUME_WORKING_DOCX_PATH.read_bytes()).hexdigest(), before)

    def test_generated_docx_builds_in_place(self) -> None:
        output_path = self.output_dir / "generated-resume.docx"
        shutil.copy2(RESUME_DOCX_OUTPUT_PATH, output_path)
        result = build_resume(self.resume_data, template_path=RESUME_WORKING_DOCX_PATH, output_path=output_path, pdf_path=None)
        self.assertEqual(result.docx_path, output_path)
        self.assertTrue(output_path.exists())
        rendered_values = read_content_control_values(output_path)
        validate_resume_document(output_path, expected_tags=set(rendered_values))
        self.assertFalse(any(not value and "_BULLET" in tag for tag, value in rendered_values.items()))

    def test_working_resume_has_valid_blank_capacity(self) -> None:
        values = read_content_control_values(RESUME_WORKING_DOCX_PATH)
        public_record = build_resume_record(self.resume_data)
        working_record = build_resume_record(self.resume_data, include_working_blanks=True)
        actual_tags = validate_resume_template_capacity(
            RESUME_WORKING_DOCX_PATH,
            required_tags=set(public_record.values),
            allowed_tags=set(working_record.values),
        )
        self.assertEqual(actual_tags, set(values))
        self.assertEqual(
            working_record.blank_entries,
            {"EDU3", "EXP3", "LEAD3", "COMM2", "RECOG4", "PROJECT8"},
        )
        for entry_key in working_record.blank_entries:
            self.assertTrue(all(not value for tag, value in values.items() if tag.startswith(entry_key + "_")))
        for tag in actual_tags - set(public_record.values):
            self.assertEqual(values[tag], "")

    def test_public_resume_removes_unused_entries_and_bullets(self) -> None:
        values = read_content_control_values(RESUME_DOCX_OUTPUT_PATH)
        self.assertFalse(any(not value and "_BULLET" in tag for tag, value in values.items()))
        for entry_key in ("EDU3", "EXP3", "LEAD3", "COMM2", "RECOG4", "PROJECT8"):
            self.assertFalse(any(tag.startswith(entry_key + "_") for tag in values))

    def test_filled_blank_entry_creates_stable_json_record_and_next_spare(self) -> None:
        values = read_content_control_values(RESUME_WORKING_DOCX_PATH)
        values.update(
            {
                "EXP3_TITLE": "New Word Role",
                "EXP3_META": "New Organization - Calgary, AB",
                "EXP3_DATES": "2026-Present",
                "EXP3_BULLET1": "New detail entered through Word.",
            }
        )
        updated = sync_word_values_into_resume(self.resume_data, values)
        experience = next(block for block in updated["pages"][0]["blocks"] if block.get("heading") == "Experience")
        added = experience["items"][-1]
        self.assertEqual(added["id"], "experience_4")
        self.assertEqual(added["role"], "New Word Role")
        self.assertEqual(added["bullets"], ["New detail entered through Word."])
        self.assertEqual(updated["_meta"]["word_slot_order"]["experience"][-1], "experience_4")
        rebuilt_working = build_resume_record(updated, include_working_blanks=True)
        self.assertIn("EXP4", rebuilt_working.blank_entries)
        self.assertEqual(rebuilt_working.values["EXP3_BULLET2"], "")

    def test_filled_extra_bullet_is_saved_and_replaced_with_a_new_blank(self) -> None:
        values = read_content_control_values(RESUME_WORKING_DOCX_PATH)
        values["EXP1_BULLET5"] = "A fifth detail added in Word."
        updated = sync_word_values_into_resume(self.resume_data, values)
        experience = next(block for block in updated["pages"][0]["blocks"] if block.get("heading") == "Experience")
        selected = next(item for item in experience["items"] if item["id"] == "experience_2")
        self.assertEqual(selected["bullets"][-1], "A fifth detail added in Word.")
        rebuilt_working = build_resume_record(updated, include_working_blanks=True)
        self.assertEqual(rebuilt_working.values["EXP1_BULLET6"], "")

    def test_pdf_conversion_prefers_isolated_libreoffice(self) -> None:
        input_path = self.output_dir / "converter-input.docx"
        output_path = self.output_dir / "converter-output.pdf"
        soffice = Path("soffice")
        with (
            patch.object(resume_build, "_find_soffice", return_value=soffice),
            patch.object(resume_build, "_convert_with_libreoffice") as libreoffice,
            patch.object(resume_build, "_convert_with_word") as word,
        ):
            backend = resume_build.convert_docx_to_pdf(input_path, output_path)

        self.assertEqual(backend, "LibreOffice headless")
        libreoffice.assert_called_once_with(
            input_path,
            output_path,
            soffice,
            timeout=resume_build.LIBREOFFICE_PDF_TIMEOUT_SECONDS,
        )
        word.assert_not_called()

    def test_pdf_conversion_falls_back_to_bounded_word_worker(self) -> None:
        input_path = self.output_dir / "fallback-input.docx"
        output_path = self.output_dir / "fallback-output.pdf"
        progress: list[str] = []
        with (
            patch.object(resume_build, "_find_soffice", return_value=Path("soffice")),
            patch.object(resume_build, "_convert_with_libreoffice", side_effect=RuntimeError("timed out")),
            patch.object(resume_build, "_convert_with_word") as word,
            patch.object(resume_build.sys, "platform", "win32"),
        ):
            backend = resume_build.convert_docx_to_pdf(input_path, output_path, progress=progress.append)

        self.assertEqual(backend, "Microsoft Word COM")
        word.assert_called_once_with(
            input_path,
            output_path,
            timeout=resume_build.WORD_PDF_TIMEOUT_SECONDS,
        )
        self.assertTrue(any("LibreOffice conversion failed" in message for message in progress))
        self.assertTrue(any("30-second limit" in message for message in progress))

    def test_word_worker_timeout_is_reported_instead_of_hanging(self) -> None:
        input_path = self.output_dir / "word-timeout-input.docx"
        output_path = self.output_dir / "word-timeout-output.pdf"
        with patch.object(
            resume_build.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="word worker", timeout=0.01),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 0.01 seconds"):
                resume_build._convert_with_word(input_path, output_path, timeout=0.01)

    def test_libreoffice_timeout_is_reported_instead_of_hanging(self) -> None:
        input_path = self.output_dir / "libreoffice-timeout-input.docx"
        output_path = self.output_dir / "libreoffice-timeout-output.pdf"
        with patch.object(
            resume_build.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="soffice", timeout=0.01),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 0.01 seconds"):
                resume_build._convert_with_libreoffice(
                    input_path,
                    output_path,
                    Path("soffice"),
                    timeout=0.01,
                )

    def test_generated_resume_theme_uses_site_design_tokens(self) -> None:
        output_path = self.output_dir / "theme-linked-resume.docx"
        tokens = load_design_tokens(DESIGN_TOKENS_PATH)
        shutil.copy2(RESUME_DOCX_OUTPUT_PATH, output_path)
        apply_resume_theme(output_path, tokens)
        with zipfile.ZipFile(output_path) as package:
            document = etree.fromstring(package.read("word/document.xml"))
            theme = etree.fromstring(package.read("word/theme/theme1.xml"))

        self.assertIn(tokens.colors["green"].removeprefix("#").upper(), document.xpath(".//w:shd/@w:fill", namespaces=NS))
        self.assertIn(tokens.colors["white"].removeprefix("#").upper(), document.xpath(".//w:color/@w:val", namespaces=NS))
        self.assertEqual(
            theme.xpath(
                "string(.//a:clrScheme/a:accent1/a:srgbClr/@val)",
                namespaces={"a": "http://schemas.openxmlformats.org/drawingml/2006/main"},
            ),
            tokens.colors["accent"].removeprefix("#").upper(),
        )
        name_run = document.xpath(".//w:sdt[w:sdtPr/w:tag/@w:val='CONTACT_NAME']//w:r[1]", namespaces=NS)[0]
        self.assertEqual(name_run.xpath("string(w:rPr/w:rFonts/@w:ascii)", namespaces=NS), "Arial")
        self.assertEqual(name_run.xpath("string(w:rPr/w:sz/@w:val)", namespaces=NS), "38")
        self.assertEqual(
            name_run.xpath("string(w:rPr/w:color/@w:val)", namespaces=NS),
            tokens.colors["green"].removeprefix("#").upper(),
        )
        self.assertTrue(name_run.xpath("boolean(w:rPr/w:b)", namespaces=NS))

    def test_only_section_headers_have_coloured_backgrounds(self) -> None:
        tokens = load_design_tokens(DESIGN_TOKENS_PATH)
        with zipfile.ZipFile(RESUME_DOCX_OUTPUT_PATH) as package:
            document = etree.fromstring(package.read("word/document.xml"))
        self.assertEqual(document.xpath(".//w:tcPr/w:shd", namespaces=NS), [])
        shaded_paragraphs = document.xpath(".//w:p[w:pPr/w:shd]", namespaces=NS)
        self.assertTrue(shaded_paragraphs)
        self.assertTrue(
            all(
                "".join(paragraph.xpath(".//w:t/text()", namespaces=NS)).strip()
                in STATIC_RESUME_TEXT_STYLES
                for paragraph in shaded_paragraphs
            )
        )
        self.assertTrue(
            all(
                color.upper() == tokens.colors["white"].removeprefix("#").upper()
                for paragraph in shaded_paragraphs
                for color in paragraph.xpath(".//w:rPr/w:color/@w:val", namespaces=NS)
            )
        )

    def test_resume_text_styles_cover_every_editable_and_static_treatment(self) -> None:
        tokens = load_design_tokens(DESIGN_TOKENS_PATH)
        editable_tags = set(read_content_control_values(RESUME_WORKING_DOCX_PATH))
        self.assertEqual({tag for tag in editable_tags if resume_text_style_for_tag(tag) is None}, set())
        expected_styles = {
            resume_text_style_for_tag(tag) for tag in editable_tags
        } | set(STATIC_RESUME_TEXT_STYLES.values())
        self.assertTrue(expected_styles.issubset(tokens.text_styles))
        for style_name in expected_styles:
            style = tokens.text_styles[style_name]
            for value in (
                style.font_family,
                style.font_size,
                style.font_weight,
                style.font_style,
                style.line_height,
                style.letter_spacing,
                style.color,
                style.text_transform,
            ):
                self.assertTrue(value)

    def test_page_two_has_seven_grouped_project_records(self) -> None:
        values = read_content_control_values(RESUME_DOCX_OUTPUT_PATH)
        for slot in range(1, 8):
            self.assertTrue(values[f"PROJECT{slot}_TITLE"].strip())
            self.assertTrue(values[f"PROJECT{slot}_META"].strip())
            self.assertTrue(values[f"PROJECT{slot}_DATES"].strip())
        self.assertEqual(
            [values.get(f"PROJECT{slot}_CATEGORY", "") for slot in range(1, 8)],
            ["Industry Projects", "", "Course Projects", "", "Extracurricular Projects", "Personal Projects", ""],
        )

    def test_word_sync_updates_a_copy_of_the_resume_model(self) -> None:
        values = read_content_control_values(RESUME_WORKING_DOCX_PATH)
        values.update(
            {
                "CONTACT_NAME": "Word Edited Name",
                "GENERAL_SKILL_1": "Word Skill",
                "EDU2_INSTITUTION": "Word Edited High School",
                "EDU2_BULLET1": "Word Edited High School Detail",
            }
        )
        updated = sync_word_values_into_resume(self.resume_data, values)
        self.assertEqual(updated["name"], "Word Edited Name")
        self.assertEqual(updated["general_skills"][0], "Word Skill")
        education = updated["pages"][0]["blocks"][0]["items"]
        self.assertEqual(education[1]["organization"], "Word Edited High School")
        self.assertEqual(education[1]["bullets"][0], "Word Edited High School Detail")
        self.assertEqual(education[1]["bullets"][1:], self.resume_data["pages"][0]["blocks"][0]["items"][1]["bullets"][1:])
        self.assertNotEqual(updated, self.resume_data)
        self.assertEqual(self.resume_data["name"], "Ashwin Conrad")

    def test_word_sync_accepts_public_document_without_blank_optional_controls(self) -> None:
        values = read_content_control_values(RESUME_DOCX_OUTPUT_PATH)
        self.assertNotIn("RECOG1_META", values)
        updated = sync_word_values_into_resume(self.resume_data, values)
        self.assertEqual(updated["name"], "Ashwin Conrad")

    def test_non_experience_resume_sections_preserve_variable_bullet_counts(self) -> None:
        record = build_resume_record(self.resume_data)
        items = {
            item["id"]: item
            for page in self.resume_data["pages"]
            for block in page.get("blocks", [])
            for item in block.get("items", [])
            if isinstance(item, dict) and item.get("include", True) and item.get("id")
        }
        _, leadership_ids, community_ids, recognition_ids, _ = word_slot_order(self.resume_data)
        for prefix, item_ids in (
            ("LEAD", leadership_ids),
            ("COMM", community_ids),
            ("RECOG", recognition_ids),
        ):
            for index, item_id in enumerate(item_ids, start=1):
                mapped = [
                    record.values[f"{prefix}{index}_BULLET{bullet_index}"]
                    for bullet_index in range(1, len(items[item_id]["bullets"]) + 1)
                ]
                self.assertEqual(mapped, items[item_id]["bullets"])

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
