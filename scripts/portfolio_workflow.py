"""Implementation for the portfolio command-line workflow.

This module keeps the operational commands in :mod:`portfolio` small while
leaving the renderer, editor, and resume package independently testable.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
from typing import Any

from content_model import (
    ContentModelError,
    compose_site_content,
    get_path,
    load_details_content,
    read_json,
    set_path,
    validate_content_model,
    write_json_atomic,
)
from design_tokens import load_design_tokens
from project_paths import (
    ASSETS_DIR,
    DESIGN_TOKENS_PATH,
    DETAILS_CONTENT_PATH,
    RESUME_CONTENT_PATH,
    RESUME_DOCX_OUTPUT_PATH,
    RESUME_OUTPUT_PATH,
    ROOT,
    SCRIPT_OUTPUT_PATH,
    SITE_CONTENT_PATH,
    SITE_OUTPUT_PATH,
    STYLES_OUTPUT_PATH,
)
from resume.build import ResumeBuildResult, build_resume
from resume.validation import ResumeValidationError, validate_pdf_page_count, validate_resume_document
from resume.word_renderer import read_content_control_values
from resume.word_sync import sync_word_values_into_resume
from site_renderer import render_engineering_index, render_engineering_styles, render_site_script


@dataclass(frozen=True)
class SiteBuildResult:
    """Paths and conversion information from a complete portfolio build."""

    resume: ResumeBuildResult


def load_content() -> dict[str, Any]:
    return compose_site_content(read_json(SITE_CONTENT_PATH), load_details_content())


def build_site() -> SiteBuildResult:
    """Regenerate the public website plus the editable Word resume and PDF."""

    data = load_content()
    resume_data = read_json(RESUME_CONTENT_PATH)
    SITE_OUTPUT_PATH.write_text(render_engineering_index(data), encoding="utf-8", newline="\n")
    STYLES_OUTPUT_PATH.write_text(
        render_engineering_styles(load_design_tokens(DESIGN_TOKENS_PATH)), encoding="utf-8", newline="\n"
    )
    SCRIPT_OUTPUT_PATH.write_text(render_site_script(), encoding="utf-8", newline="\n")
    resume = build_resume(resume_data, docx_path=RESUME_DOCX_OUTPUT_PATH, pdf_path=RESUME_OUTPUT_PATH)
    return SiteBuildResult(resume=resume)


def build_resume_artifacts(*, validate_only: bool = False, docx_only: bool = False) -> ResumeBuildResult:
    """Build or validate just the resume artifact pair."""

    return build_resume(
        read_json(RESUME_CONTENT_PATH),
        docx_path=RESUME_DOCX_OUTPUT_PATH,
        pdf_path=None if validate_only or docx_only else RESUME_OUTPUT_PATH,
        validate_only=validate_only,
    )


def sync_shared_fields(site_data: dict, resume_data: dict, *, force: bool = False) -> tuple[dict, list[str]]:
    """Safely copy the resume's explicitly shared factual fields from the site."""

    updated = deepcopy(resume_data)
    meta = updated.get("_meta", {})
    fields = meta.get("shared_fields", []) if isinstance(meta, dict) else []
    if not isinstance(fields, list):
        raise ContentModelError("resume._meta.shared_fields must be a list")
    report: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            raise ContentModelError("Every resume shared field must be an object")
        source_path = field.get("source")
        target_path = field.get("target")
        label = field.get("label", target_path)
        if not isinstance(source_path, str) or not isinstance(target_path, str):
            raise ContentModelError("Every resume shared field needs source and target paths")
        source_value = get_path(site_data, source_path)
        target_value = get_path(updated, target_path)
        previous_value = field.get("last_synced_value")
        if target_value == source_value:
            field["last_synced_value"] = source_value
            report.append(f"Current: {label}")
        elif force or target_value == previous_value:
            set_path(updated, target_path, source_value)
            field["last_synced_value"] = source_value
            report.append(f"Updated: {label}")
        else:
            report.append(f"Kept resume override: {label}")
    return updated, report


def sync_word_resume() -> SiteBuildResult:
    """Import intentional Word Content Control edits and refresh public output."""

    validate_resume_document(RESUME_DOCX_OUTPUT_PATH)
    updated = sync_word_values_into_resume(
        read_json(RESUME_CONTENT_PATH), read_content_control_values(RESUME_DOCX_OUTPUT_PATH)
    )
    write_json_atomic(RESUME_CONTENT_PATH, updated)
    return build_site()


class _HtmlCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, {key: value or "" for key, value in attrs}))


def validate_site() -> list[str]:
    """Validate authored content, generated links, and deployable outputs."""

    errors: list[str] = []
    site_data = _load_json(SITE_CONTENT_PATH, errors)
    resume_data = _load_json(RESUME_CONTENT_PATH, errors)
    try:
        details_data = load_details_content()
    except ContentModelError as error:
        errors.append(str(error))
        details_data = None
    if errors:
        return errors

    _require_mapping(site_data, SITE_CONTENT_PATH, errors)
    _require_mapping(details_data, DETAILS_CONTENT_PATH, errors)
    _require_mapping(resume_data, RESUME_CONTENT_PATH, errors)
    if errors:
        return errors

    _require_keys(site_data, ("site", "identity", "navigation"), "content/site.json", errors)
    portfolio = details_data.get("portfolio")
    if not isinstance(portfolio, dict):
        errors.append("the details collection must contain a portfolio object")
    else:
        _require_keys(
            portfolio,
            (
                "hero",
                "profile",
                "case_studies",
                "experience",
                "skills",
                "documentation",
                "leadership",
                "personal_builds",
                "contact",
            ),
            "details.portfolio",
            errors,
        )

    errors.extend(validate_content_model(site_data, details_data, resume_data))
    referenced_photos: set[str] = set()
    _validate_content_paths(site_data, "content/site.json", referenced_photos, errors)
    _validate_content_paths(details_data, "content/details", referenced_photos, errors)
    _validate_photo_inventory(referenced_photos, errors)

    try:
        rendered_html = render_engineering_index(load_content())
    except Exception as error:  # pragma: no cover - exercised through failure diagnostics
        errors.append(f"site renderer failed: {error}")
    else:
        _validate_rendered_html(rendered_html, errors)
    _validate_public_outputs(errors)
    return errors


def generated_drift() -> list[str]:
    """Return public artifacts that differ from the current structured sources."""

    issues: list[str] = []
    try:
        data = load_content()
    except Exception as error:  # pragma: no cover - failure is reported by CLI
        return [f"could not load site content: {error}"]
    expected = {
        SITE_OUTPUT_PATH: render_engineering_index(data),
        STYLES_OUTPUT_PATH: render_engineering_styles(load_design_tokens(DESIGN_TOKENS_PATH)),
        SCRIPT_OUTPUT_PATH: render_site_script(),
    }
    for path, rendered in expected.items():
        if not path.exists():
            issues.append(f"{path.relative_to(ROOT)} is missing; run python scripts/portfolio.py build")
        elif path.read_text(encoding="utf-8") != rendered:
            issues.append(f"{path.relative_to(ROOT)} is out of date; run python scripts/portfolio.py build")
    try:
        validate_pdf_page_count(RESUME_OUTPUT_PATH)
    except ResumeValidationError as error:
        issues.append(str(error))
    return issues


def prepare_pages_artifact(artifact_dir: Path | None = None) -> Path:
    """Create a clean GitHub Pages artifact from public files only."""

    target = (artifact_dir or ROOT / "_site").resolve()
    root = ROOT.resolve()
    if target == root or root not in target.parents:
        raise RuntimeError(f"Refusing to prepare artifact outside the repository: {target}")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for source in (SITE_OUTPUT_PATH, STYLES_OUTPUT_PATH, SCRIPT_OUTPUT_PATH):
        _copy_file(source, target / source.relative_to(ROOT))
    shutil.copytree(ASSETS_DIR, target / "assets")
    portfolio_dir = target / "portfolio"
    portfolio_dir.mkdir()
    _copy_file(RESUME_OUTPUT_PATH, portfolio_dir / RESUME_OUTPUT_PATH.name)
    (target / ".nojekyll").write_text("", encoding="utf-8")
    return target


def _load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        errors.append(f"{path.relative_to(ROOT)} is not valid JSON: {error}")
        return None


def _require_mapping(value: Any, path: Path, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)} must contain a JSON object")


def _require_keys(value: dict[str, Any], keys: tuple[str, ...], label: str, errors: list[str]) -> None:
    for key in keys:
        if key not in value:
            errors.append(f"{label} is missing required key: {key}")


def _validate_content_paths(value: Any, location: str, referenced_photos: set[str], errors: list[str]) -> None:
    if isinstance(value, dict):
        src = value.get("src")
        if isinstance(src, str):
            _validate_local_reference(src, f"{location}.src", errors)
            if src.startswith("assets/photos/"):
                referenced_photos.add(src)
                if not str(value.get("alt", "")).strip():
                    errors.append(f"{location} references {src} without non-empty alt text")
            if not src and str(value.get("alt", "")).strip():
                errors.append(f"{location} has alt text but no image source")
        for key, child in value.items():
            _validate_content_paths(child, f"{location}.{key}", referenced_photos, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_content_paths(child, f"{location}[{index}]", referenced_photos, errors)


def _validate_photo_inventory(referenced_photos: set[str], errors: list[str]) -> None:
    photo_dir = ASSETS_DIR / "photos"
    if not photo_dir.exists():
        errors.append("assets/photos directory is missing")
        return
    existing = {
        path.relative_to(ROOT).as_posix()
        for path in photo_dir.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    }
    for missing in sorted(referenced_photos - existing):
        errors.append(f"referenced photo does not exist: {missing}")


def _validate_rendered_html(html: str, errors: list[str]) -> None:
    parser = _HtmlCollector()
    parser.feed(html)
    ids = {attrs["id"] for _, attrs in parser.elements if attrs.get("id")}
    for tag, attrs in parser.elements:
        if tag == "a":
            _validate_anchor(attrs, ids, errors)
        if tag == "img":
            src = attrs.get("src", "")
            if src and not attrs.get("alt", "").strip():
                errors.append(f"rendered image {src} is missing non-empty alt text")
        for attr in ("src", "href"):
            value = attrs.get(attr, "")
            if value:
                _validate_local_reference(value, f"rendered {tag}[{attr}]", errors)


def _validate_anchor(attrs: dict[str, str], ids: set[str], errors: list[str]) -> None:
    href = attrs.get("href", "")
    if href.startswith("#") and href != "#" and href[1:] not in ids:
        errors.append(f"rendered anchor points at missing id: {href}")
    if attrs.get("target") == "_blank":
        rel_tokens = set(attrs.get("rel", "").split())
        if not ({"noopener", "noreferrer"} & rel_tokens):
            errors.append(f"rendered external link {href} uses target=_blank without noopener or noreferrer")


def _validate_local_reference(value: str, location: str, errors: list[str]) -> None:
    if not value or value.startswith(("#", "data:", "mailto:", "http://", "https://")):
        return
    path_part = value.split("#", 1)[0].split("?", 1)[0]
    if path_part and not (ROOT / path_part).exists():
        errors.append(f"{location} references missing local file: {value}")


def _validate_public_outputs(errors: list[str]) -> None:
    for path in (SITE_OUTPUT_PATH, STYLES_OUTPUT_PATH, SCRIPT_OUTPUT_PATH, RESUME_OUTPUT_PATH):
        if not path.exists():
            errors.append(f"deployable output is missing: {path.relative_to(ROOT)}")


def _copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Required deploy file is missing: {source.relative_to(ROOT)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
