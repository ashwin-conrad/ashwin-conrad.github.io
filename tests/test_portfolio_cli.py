from __future__ import annotations

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import portfolio  # noqa: E402
import portfolio_workflow  # noqa: E402


class PortfolioCliTests(unittest.TestCase):
    def test_menu_is_numbered_and_grouped_by_purpose(self) -> None:
        answers = iter(("wrong", "1", "0", "0"))
        output: list[str] = []

        result = portfolio.run_interactive(lambda _prompt: next(answers), output.append)

        menu_text = "\n".join(output)
        self.assertEqual(result, 0)
        self.assertIn("1. Build & release", menu_text)
        self.assertIn("2. Working content", menu_text)
        self.assertIn("3. Resume", menu_text)
        self.assertIn("4. Quality checks", menu_text)
        self.assertIn("Enter a number from 0 to 4.", menu_text)
        self.assertIn("1. Rebuild everything", menu_text)

    def test_working_resume_creation_requires_force_outside_the_menu(self) -> None:
        with TemporaryDirectory() as temporary:
            working_resume = Path(temporary) / "resume-working.docx"
            working_resume.touch()
            with (
                patch.object(portfolio, "RESUME_WORKING_DOCX_PATH", working_resume),
                patch.object(portfolio, "create_working_resume") as create_resume,
            ):
                self.assertEqual(portfolio._new_working_resume(argparse.Namespace(force=False)), 1)
                create_resume.assert_not_called()

                self.assertEqual(portfolio._new_working_resume(argparse.Namespace(force=True)), 0)
                create_resume.assert_called_once_with()

    def test_working_resume_menu_action_forwards_force_after_confirmation(self) -> None:
        action = portfolio.MENU_GROUPS[1].actions[4]
        with (
            patch.object(portfolio, "_confirm_working_replacement", return_value=True),
            patch.object(portfolio, "main", return_value=0) as run_command,
        ):
            self.assertEqual(portfolio._run_menu_action(action, input, print), 0)
        run_command.assert_called_once_with(["new-working-resume", "--force"])

    def test_shared_working_menu_action_creates_both_documents(self) -> None:
        action = portfolio.MENU_GROUPS[1].actions[0]
        with (
            patch.object(portfolio, "_confirm_working_replacement", return_value=True),
            patch.object(portfolio, "main", return_value=0) as run_command,
        ):
            self.assertEqual(portfolio._run_menu_action(action, input, print), 0)
        run_command.assert_called_once_with(["new-working", "--force"])

    def test_new_working_resume_is_populated_from_json(self) -> None:
        with TemporaryDirectory() as temporary:
            working_resume = Path(temporary) / "resume-working.docx"
            with patch.object(portfolio_workflow, "RESUME_WORKING_DOCX_PATH", working_resume):
                portfolio_workflow.create_working_resume()

            values = portfolio_workflow.read_content_control_values(working_resume)
            self.assertEqual(values["CONTACT_NAME"], "Ashwin Conrad")
            self.assertNotEqual(values["PROFILE_SUMMARY"], "Professional summary")
            self.assertTrue(values["PROFILE_SUMMARY"])

    def test_word_sync_reads_the_editable_working_resume(self) -> None:
        sentinel = object()
        with (
            patch.object(portfolio_workflow, "validate_resume_template_capacity"),
            patch.object(portfolio_workflow, "load_resume_content", return_value={}),
            patch.object(portfolio_workflow, "read_json", return_value={}),
            patch.object(portfolio_workflow, "resolve_fact_references", side_effect=lambda value, _facts: value),
            patch.object(portfolio_workflow, "read_content_control_values", return_value={}) as read_values,
            patch.object(portfolio_workflow, "sync_word_values_into_resume", return_value={}),
            patch.object(portfolio_workflow, "restore_fact_references", return_value={}),
            patch.object(portfolio_workflow, "build_resume_record") as build_record,
            patch.object(portfolio_workflow, "write_resume_content"),
            patch.object(portfolio_workflow, "build_site", return_value=sentinel),
        ):
            build_record.return_value.values = {}
            self.assertIs(portfolio_workflow.sync_word_resume(), sentinel)

        read_values.assert_called_once_with(portfolio_workflow.RESUME_WORKING_DOCX_PATH)

    def test_shared_word_sync_stages_both_documents_before_writing(self) -> None:
        sentinel = object()
        progress: list[str] = []
        with (
            patch.object(portfolio_workflow, "_read_working_resume_update", return_value={}) as read_resume,
            patch.object(portfolio_workflow, "read_working_website_updates", return_value=[]) as read_website,
            patch.object(portfolio_workflow, "write_resume_content") as write_resume,
            patch.object(portfolio_workflow, "write_website_updates") as write_website,
            patch.object(portfolio_workflow, "build_site", return_value=sentinel) as build,
        ):
            self.assertIs(portfolio_workflow.sync_working_documents(progress=progress.append), sentinel)

        read_resume.assert_called_once_with(progress=progress.append)
        read_website.assert_called_once_with(portfolio_workflow.WEBSITE_WORKING_DOCX_PATH)
        write_resume.assert_called_once_with({})
        write_website.assert_called_once_with([])
        build.assert_called_once_with(progress=progress.append)
        self.assertTrue(any("Reading and validating" in message for message in progress))
        self.assertTrue(any("Rebuilding public" in message for message in progress))


if __name__ == "__main__":
    unittest.main()
