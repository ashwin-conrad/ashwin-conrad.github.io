"""One command-line entry point for developing and publishing the portfolio.

Run these from the repository root:

    python scripts/portfolio.py editor
    python scripts/portfolio.py build
    python scripts/portfolio.py build --resume-only --docx-only
    python scripts/portfolio.py check
    python scripts/portfolio.py sync-shared
    python scripts/portfolio.py sync-shared --apply
    python scripts/portfolio.py sync-shared --apply --force
    python scripts/portfolio.py sync-word
    python scripts/portfolio.py prepare-pages
"""

from __future__ import annotations

import argparse

from content_editor import main as run_editor
from portfolio_workflow import (
    build_resume_artifacts,
    build_site,
    generated_drift,
    prepare_pages_artifact,
    sync_shared_fields,
    sync_word_resume,
    validate_site,
)
from content_model import read_json, write_json_atomic
from project_paths import RESUME_CONTENT_PATH, ROOT, SITE_CONTENT_PATH
from resume.word_renderer import DocumentReplaceError


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
    updated, report = sync_shared_fields(read_json(SITE_CONTENT_PATH), read_json(RESUME_CONTENT_PATH), force=args.force)
    for line in report:
        print(f"- {line}")
    if args.apply:
        write_json_atomic(RESUME_CONTENT_PATH, updated)
        print("Saved content/resume.json.")
    else:
        print("Dry run only. Re-run with sync-shared --apply to save safe updates.")
    return 0


def _sync_word() -> int:
    try:
        result = sync_word_resume()
    except DocumentReplaceError as error:
        print(f"Resume sync failed: {error}")
        return 1
    print(
        "Imported Word resume edits into content/resume.json and rebuilt the website and resume "
        f"via {result.resume.pdf_backend}."
    )
    return 0


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Build, edit, validate, and publish the portfolio")
    commands = command_parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Regenerate website, Word resume, and PDF")
    build.add_argument("--resume-only", action="store_true", help="Build only the resume artifacts")
    build.add_argument("--docx-only", action="store_true", help="With --resume-only, skip PDF conversion")
    build.set_defaults(handler=_build)

    check = commands.add_parser("check", help="Validate source, resume template, and generated output")
    check.set_defaults(handler=lambda _args: _check())

    editor = commands.add_parser("editor", help="Run the local browser content editor")
    editor.add_argument("--port", type=int, default=4173, help="Local port (default: 4173)")
    editor.set_defaults(handler=lambda args: run_editor(["--port", str(args.port)]))

    shared = commands.add_parser("sync-shared", help="Preview or apply explicitly shared site facts to the resume")
    shared.add_argument("--apply", action="store_true", help="Write safe updates to content/resume.json")
    shared.add_argument("--force", action="store_true", help="Overwrite independently edited resume values")
    shared.set_defaults(handler=_sync_shared)

    word = commands.add_parser("sync-word", help="Import Word Content Control edits into JSON and rebuild")
    word.set_defaults(handler=lambda _args: _sync_word())

    pages = commands.add_parser("prepare-pages", help="Create the clean _site GitHub Pages artifact")
    pages.set_defaults(handler=lambda _args: _prepare_pages())
    return command_parser


def _prepare_pages() -> int:
    target = prepare_pages_artifact()
    print(f"Prepared GitHub Pages artifact at {target.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
