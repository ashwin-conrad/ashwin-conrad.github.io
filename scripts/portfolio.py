"""Interactive command-line workflow for the portfolio.

Run ``python scripts/portfolio.py`` from the repository root to open the
numbered menu. Named subcommands remain available for CI and repeatable
automation; use ``python scripts/portfolio.py --help`` to see them.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import subprocess
import sys

from content_model import load_resume_content, read_json, write_resume_content
from portfolio_workflow import (
    build_resume_artifacts,
    build_site,
    create_working_resume,
    generated_drift,
    prepare_pages_artifact,
    sync_shared_fields,
    sync_word_resume,
    validate_site,
)
from project_paths import FACTS_CONTENT_PATH, RESUME_WORKING_DOCX_PATH, ROOT, SITE_CONTENT_PATH
from resume.word_renderer import DocumentReplaceError


Input = Callable[[str], str]
Output = Callable[[str], None]


@dataclass(frozen=True)
class MenuAction:
    """A numbered workflow action shown inside an interactive menu."""

    label: str
    description: str
    argv: tuple[str, ...]
    confirms_replacement: bool = False


@dataclass(frozen=True)
class MenuGroup:
    """A purpose-based group of workflow actions."""

    title: str
    description: str
    actions: tuple[MenuAction, ...]


MENU_GROUPS = (
    MenuGroup(
        "Build & release",
        "Regenerate public files and prepare the GitHub Pages artifact.",
        (
            MenuAction("Rebuild everything", "Website HTML, CSS, JavaScript, public Word resume, and PDF.", ("build",)),
            MenuAction("Prepare GitHub Pages files", "Create the clean _site artifact from the current public files.", ("prepare-pages",)),
            MenuAction(
                "Rebuild and prepare GitHub Pages files",
                "Regenerate every public file, then create the clean _site artifact.",
                ("build-pages",),
            ),
        ),
    ),
    MenuGroup(
        "Resume",
        "Create, import, synchronize, and generate resume artifacts.",
        (
            MenuAction(
                "Create a fresh working Word resume",
                "Replace the editable two-page resume with a populated copy of the current JSON content.",
                ("new-working-resume", "--force"),
                confirms_replacement=True,
            ),
            MenuAction("Build the public Word resume and PDF", "Generate portfolio/resume.docx and portfolio/resume.pdf.", ("build", "--resume-only")),
            MenuAction("Build the public Word resume only", "Generate portfolio/resume.docx without PDF conversion.", ("build", "--resume-only", "--docx-only")),
            MenuAction(
                "Sync Word edits to JSON and rebuild everything",
                "Read portfolio/resume-working.docx, update canonical resume JSON, then rebuild all public outputs.",
                ("sync-word",),
            ),
            MenuAction("Preview shared facts sync", "Show safe site or facts updates that could be applied to the resume.", ("sync-shared",)),
            MenuAction("Apply safe shared facts sync", "Save only shared fields that have not been independently overridden.", ("sync-shared", "--apply")),
            MenuAction("Force shared facts sync", "Overwrite independent resume values for every configured shared field.", ("sync-shared", "--apply", "--force")),
        ),
    ),
    MenuGroup(
        "Quality checks",
        "Verify structured content, generated artifacts, and the automated test suite.",
        (
            MenuAction("Check content and generated output", "Validate sources, Word controls, links, and generated-file drift.", ("check",)),
            MenuAction("Run the test suite", "Run all repository tests.", ("test",)),
        ),
    ),
)


def _print_issues(title: str, issues: list[str]) -> int:
    if issues:
        print(f"{title} failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"{title} passed.")
    return 0


def _build(args: argparse.Namespace) -> int:
    try:
        if args.resume_only:
            result = build_resume_artifacts(docx_only=args.docx_only)
            if args.docx_only:
                print("Built portfolio/resume.docx")
            else:
                print(f"Built portfolio/resume.docx and portfolio/resume.pdf via {result.pdf_backend}")
            return 0
        if args.docx_only:
            raise SystemExit("--docx-only can only be used with --resume-only")
        result = build_site()
        print(
            "Built index.html, styles.css, script.js, portfolio/resume.docx, and "
            f"portfolio/resume.pdf via {result.resume.pdf_backend}"
        )
        return 0
    except DocumentReplaceError as error:
        print(f"Build failed: {error}")
        return 1


def _build_pages() -> int:
    result = _build(argparse.Namespace(resume_only=False, docx_only=False))
    return _prepare_pages() if result == 0 else result


def _check() -> int:
    errors = validate_site()
    try:
        result = build_resume_artifacts(validate_only=True)
    except Exception as error:
        errors.append(f"resume validation failed: {error}")
    else:
        print(f"Validated {len(result.record.values)} Word Content Control mappings")
    errors.extend(generated_drift())
    return _print_issues("Portfolio check", errors)


def _sync_shared(args: argparse.Namespace) -> int:
    updated, report = sync_shared_fields(
        read_json(SITE_CONTENT_PATH), load_resume_content(), read_json(FACTS_CONTENT_PATH), force=args.force
    )
    for line in report:
        print(f"- {line}")
    if args.apply:
        write_resume_content(updated)
        print("Saved content/details/resume.json.")
    else:
        print("Dry run only. Select 'Apply safe shared facts sync' to save safe updates.")
    return 0


def _sync_word() -> int:
    try:
        result = sync_word_resume()
    except DocumentReplaceError as error:
        print(f"Resume sync failed: {error}")
        return 1
    print(
        "Imported working Word resume edits into content/details/resume.json and rebuilt the website and resume "
        f"via {result.resume.pdf_backend}."
    )
    return 0


def _new_working_resume(args: argparse.Namespace) -> int:
    if RESUME_WORKING_DOCX_PATH.exists() and not args.force:
        print(
            "A working resume already exists. Refusing to replace it without --force; "
            "use the interactive Resume menu for a confirmation prompt."
        )
        return 1
    create_working_resume()
    print("Created portfolio/resume-working.docx from the current JSON. Enter Word edits there, then select the Word-to-JSON sync action.")
    return 0


def _prepare_pages() -> int:
    target = prepare_pages_artifact()
    print(f"Prepared GitHub Pages artifact at {target.relative_to(ROOT)}")
    return 0


def _run_tests() -> int:
    print("Running repository tests...")
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT, check=False
    )
    return completed.returncode


def _prompt_choice(title: str, options: tuple[str, ...], input_fn: Input, output_fn: Output) -> int | None:
    """Show a numbered index and return the selected zero-based option."""

    output_fn("")
    output_fn(title)
    for index, option in enumerate(options, start=1):
        output_fn(f"  {index}. {option}")
    output_fn("  0. Back" if title != "Portfolio workflow" else "  0. Exit")
    while True:
        try:
            raw_value = input_fn("Enter a number: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("\nNo selection received. Exiting.")
            return None
        if raw_value == "0":
            return -1
        try:
            choice = int(raw_value)
        except ValueError:
            choice = -2
        if 1 <= choice <= len(options):
            return choice - 1
        output_fn(f"Enter a number from 0 to {len(options)}.")


def _confirm_working_resume_replacement(input_fn: Input, output_fn: Output) -> bool:
    if not RESUME_WORKING_DOCX_PATH.exists():
        return True
    output_fn("")
    output_fn("This replaces portfolio/resume-working.docx and discards any Word-only edits in that file.")
    try:
        answer = input_fn("Type REPLACE to continue: ").strip()
    except (EOFError, KeyboardInterrupt):
        output_fn("\nWorking resume was not replaced.")
        return False
    if answer == "REPLACE":
        return True
    output_fn("Working resume was not replaced.")
    return False


def _run_menu_action(action: MenuAction, input_fn: Input, output_fn: Output) -> int | None:
    if action.confirms_replacement and not _confirm_working_resume_replacement(input_fn, output_fn):
        return None
    try:
        return main(list(action.argv))
    except Exception as error:  # Keep the interactive session available after operational failures.
        output_fn(f"Action failed: {error}")
        return 1


def run_interactive(input_fn: Input = input, output_fn: Output = print) -> int:
    """Run the purpose-organized numbered workflow menu."""

    while True:
        group_index = _prompt_choice(
            "Portfolio workflow", tuple(f"{group.title} - {group.description}" for group in MENU_GROUPS), input_fn, output_fn
        )
        if group_index in (None, -1):
            output_fn("Goodbye.")
            return 0

        group = MENU_GROUPS[group_index]
        while True:
            action_index = _prompt_choice(
                group.title,
                tuple(f"{action.label} - {action.description}" for action in group.actions),
                input_fn,
                output_fn,
            )
            if action_index in (None, -1):
                break
            result = _run_menu_action(group.actions[action_index], input_fn, output_fn)
            if result is None:
                output_fn(f"'{group.actions[action_index].label}' was cancelled.")
            elif result:
                output_fn(f"'{group.actions[action_index].label}' did not complete (exit code {result}).")
            else:
                output_fn(f"'{group.actions[action_index].label}' completed.")


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Interactive workflow for building and maintaining the portfolio")
    commands = command_parser.add_subparsers(dest="command")

    commands.add_parser("menu", help="Open the interactive numbered menu")

    build = commands.add_parser("build", help="Regenerate website, Word resume, and PDF")
    build.add_argument("--resume-only", action="store_true", help="Build only the resume artifacts")
    build.add_argument("--docx-only", action="store_true", help="With --resume-only, skip PDF conversion")
    build.set_defaults(handler=_build)

    pages_build = commands.add_parser("build-pages", help="Rebuild all public files and prepare the GitHub Pages artifact")
    pages_build.set_defaults(handler=lambda _args: _build_pages())

    check = commands.add_parser("check", help="Validate source, resume template, and generated output")
    check.set_defaults(handler=lambda _args: _check())

    tests = commands.add_parser("test", help="Run the repository test suite")
    tests.set_defaults(handler=lambda _args: _run_tests())

    shared = commands.add_parser("sync-shared", help="Preview or apply explicitly shared site facts to the resume")
    shared.add_argument("--apply", action="store_true", help="Write safe updates to content/details/resume.json")
    shared.add_argument("--force", action="store_true", help="Overwrite independently edited resume values")
    shared.set_defaults(handler=_sync_shared)

    word = commands.add_parser("sync-word", help="Import editable working Word resume edits into JSON and rebuild")
    word.set_defaults(handler=lambda _args: _sync_word())

    working = commands.add_parser("new-working-resume", help="Create a fresh editable Word resume template")
    working.add_argument("--force", action="store_true", help="Replace an existing working resume")
    working.set_defaults(handler=_new_working_resume)

    pages = commands.add_parser("prepare-pages", help="Create the clean _site GitHub Pages artifact")
    pages.set_defaults(handler=lambda _args: _prepare_pages())
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command in (None, "menu"):
        return run_interactive()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
