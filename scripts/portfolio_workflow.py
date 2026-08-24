"""Implementation for the portfolio command-line workflow.

This module keeps the operational commands in :mod:`portfolio` small while
leaving the renderer, editor, and resume package independently testable.
"""

from __future__ import annotations

from collections.abc import Callable
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
    load_resume_content,
    read_json,
    resolve_fact_references,
    restore_fact_references,
    set_path,
    validate_content_model,
    write_json_atomic,
    write_resume_content,
)
from design_tokens import load_design_tokens
from project_paths import (
    ASSETS_DIR,
    ASSET_RECORD_PATH,
    DESIGN_TOKENS_PATH,
    FACTS_CONTENT_PATH,
    RESUME_CONTENT_PATH,
    RESUME_DOCX_OUTPUT_PATH,
    RESUME_WORKING_DOCX_PATH,
    RESUME_OUTPUT_PATH,
    ROOT,
    SCRIPT_OUTPUT_PATH,
    SITE_CONTENT_PATH,
    SITE_OUTPUT_PATH,
    STYLES_OUTPUT_PATH,
    WEBSITE_WORKING_DOCX_PATH,
)
from resume.build import ResumeBuildResult, build_resume
from resume.mapper import build_resume_record
from resume.template_builder import create_resume_template
from resume.theme import apply_resume_theme
from resume.validation import (
    ResumeValidationError,
    validate_pdf_page_count,
    validate_record,
    validate_resume_document,
    validate_resume_template_capacity,
)
from resume.word_renderer import read_content_control_values, render_word_template
from resume.word_sync import sync_word_values_into_resume
from site_renderer import render_engineering_index, render_engineering_styles, render_site_script
from website_working import (
    create_working_website,
    read_working_website_updates,
    write_website_updates,
)


@dataclass(frozen=True)
class SiteBuildResult:
    """Paths and conversion information from a complete portfolio build."""

    resume: ResumeBuildResult


ProgressCallback = Callable[[str], None]


def load_content() -> dict[str, Any]:
    return compose_site_content(
        read_json(SITE_CONTENT_PATH), load_details_content(), read_json(FACTS_CONTENT_PATH), read_json(ASSET_RECORD_PATH)
    )


def build_site(*, progress: ProgressCallback | None = None) -> SiteBuildResult:
    """Regenerate the public website plus the editable Word resume and PDF."""

    _report(progress, "Loading and rendering website content...")
    data = load_content()
    resume_data = resolve_fact_references(load_resume_content(), read_json(FACTS_CONTENT_PATH))
    design_tokens = load_design_tokens(DESIGN_TOKENS_PATH)
    SITE_OUTPUT_PATH.write_text(render_engineering_index(data), encoding="utf-8", newline="\n")
    STYLES_OUTPUT_PATH.write_text(render_engineering_styles(design_tokens), encoding="utf-8", newline="\n")
    SCRIPT_OUTPUT_PATH.write_text(render_site_script(), encoding="utf-8", newline="\n")
    resume = build_resume(
        resume_data,
        template_path=RESUME_WORKING_DOCX_PATH,
        output_path=RESUME_DOCX_OUTPUT_PATH,
        pdf_path=RESUME_OUTPUT_PATH,
        design_tokens=design_tokens,
        progress=progress,
    )
    return SiteBuildResult(resume=resume)


def build_resume_artifacts(
    *,
    validate_only: bool = False,
    docx_only: bool = False,
    progress: ProgressCallback | None = None,
) -> ResumeBuildResult:
    """Build or validate just the resume artifact pair."""

    return build_resume(
        resolve_fact_references(load_resume_content(), read_json(FACTS_CONTENT_PATH)),
        template_path=RESUME_WORKING_DOCX_PATH,
        output_path=RESUME_DOCX_OUTPUT_PATH,
        pdf_path=None if validate_only or docx_only else RESUME_OUTPUT_PATH,
        validate_only=validate_only,
        design_tokens=load_design_tokens(DESIGN_TOKENS_PATH),
        progress=progress,
    )


def create_working_resume() -> None:
    """Create a populated, editable Word resume from the current JSON content.

    The working document keeps every control, including optional empty fields,
    so it remains a valid source for later Word-to-JSON synchronization.
    """

    resume_data = resolve_fact_references(load_resume_content(), read_json(FACTS_CONTENT_PATH))
    record = build_resume_record(resume_data, include_working_blanks=True)
    validate_record(record)
    create_resume_template(RESUME_WORKING_DOCX_PATH, set(record.values))
    render_word_template(RESUME_WORKING_DOCX_PATH, RESUME_WORKING_DOCX_PATH, record.values)
    apply_resume_theme(RESUME_WORKING_DOCX_PATH, load_design_tokens(DESIGN_TOKENS_PATH))
    validate_resume_document(RESUME_WORKING_DOCX_PATH, expected_tags=set(record.values))


def create_working_documents() -> None:
    """Refresh both editable Word projections from canonical JSON."""

    create_working_resume()
    create_working_website(WEBSITE_WORKING_DOCX_PATH)


def sync_shared_fields(
    site_data: dict, resume_data: dict, facts_data: dict | None = None, *, force: bool = False
) -> tuple[dict, list[str]]:
    """Safely copy the resume's explicitly shared factual fields from facts."""

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
        source_data = facts_data if source_path.startswith("facts.") else site_data
        source_key = source_path.removeprefix("facts.") if source_path.startswith("facts.") else source_path
        if source_data is None:
            raise ContentModelError("content/details/facts.json is required for facts shared fields")
        source_value = get_path(source_data, source_key)
        target_node = get_path(updated, target_path)
        target_value = (
            resolve_fact_references(target_node, facts_data)
            if isinstance(target_node, dict) and "$source" in target_node and facts_data is not None
            else target_node
        )
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


def _read_working_resume_update(*, progress: ProgressCallback | None = None) -> dict[str, Any]:
    """Stage the working resume import without writing or rebuilding."""

    _report(progress, "Reading and validating content/working/resume-working.docx...")
    original = load_resume_content()
    facts = read_json(FACTS_CONTENT_PATH)
    resolved = resolve_fact_references(original, facts)
    required = build_resume_record(resolved)
    allowed = build_resume_record(resolved, include_working_blanks=True)
    validate_resume_template_capacity(
        RESUME_WORKING_DOCX_PATH,
        required_tags=set(required.values),
        allowed_tags=set(allowed.values),
    )
    updated = sync_word_values_into_resume(
        resolved, read_content_control_values(RESUME_WORKING_DOCX_PATH)
    )
    return restore_fact_references(original, updated, facts)


def sync_word_resume(*, progress: ProgressCallback | None = None) -> SiteBuildResult:
    """Import intentional resume Word edits and refresh public output."""

    resume_update = _read_working_resume_update(progress=progress)
    _report(progress, "Writing resume edits to canonical JSON...")
    write_resume_content(resume_update)
    _report(progress, "Rebuilding public website and resume artifacts...")
    return build_site(progress=progress)


def sync_word_website(*, progress: ProgressCallback | None = None) -> SiteBuildResult:
    """Import intentional website Word edits and refresh public output."""

    _report(progress, "Reading and validating content/working/website-working.docx...")
    updates = read_working_website_updates(WEBSITE_WORKING_DOCX_PATH)
    _report(progress, "Writing website edits to canonical JSON...")
    write_website_updates(updates)
    _report(progress, "Rebuilding public website and resume artifacts...")
    return build_site(progress=progress)


def sync_working_documents(*, progress: ProgressCallback | None = None) -> SiteBuildResult:
    """Import both working Word files, then rebuild all public artifacts once."""

    # Stage and validate both projections before changing any canonical source.
    resume_update = _read_working_resume_update(progress=progress)
    _report(progress, "Reading and validating content/working/website-working.docx...")
    website_updates = read_working_website_updates(WEBSITE_WORKING_DOCX_PATH)
    _report(progress, "Writing both Word projections to canonical JSON...")
    write_resume_content(resume_update)
    write_website_updates(website_updates)
    _report(progress, "Rebuilding public website and resume artifacts...")
    return build_site(progress=progress)


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
    facts_data = _load_json(FACTS_CONTENT_PATH, errors)
    asset_data = _load_json(ASSET_RECORD_PATH, errors)
    try:
        resume_data = load_resume_content()
    except ContentModelError as error:
        errors.append(str(error))
        resume_data = None
    try:
        details_data = load_details_content()
    except ContentModelError as error:
        errors.append(str(error))
        details_data = None
    if errors:
        return errors

    _require_mapping(site_data, SITE_CONTENT_PATH, errors)
    _require_mapping(facts_data, FACTS_CONTENT_PATH, errors)
    _require_mapping(asset_data, ASSET_RECORD_PATH, errors)
    _require_mapping(resume_data, RESUME_CONTENT_PATH, errors)
    if errors:
        return errors

    _require_keys(site_data, ("site", "identity", "navigation"), "content/site.json", errors)
    website = details_data.get("website")
    if not isinstance(website, dict):
        errors.append("content/site.json must contain a website object")
    else:
        _require_keys(
            website,
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
            "website",
            errors,
        )

    errors.extend(validate_content_model(site_data, details_data, resume_data, facts_data))
    try:
        composed_site = compose_site_content(site_data, details_data, facts_data, asset_data)
    except ContentModelError as error:
        errors.append(str(error))
        composed_site = None
    referenced_photos: set[str] = set()
    if composed_site is not None:
        _validate_content_paths(composed_site, "composed content", referenced_photos, errors)
    _validate_content_paths(asset_data, "content/assets/asset-record.json", referenced_photos, errors)
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
        errors.append("content/assets/photos directory is missing")
        return
    existing = {
        (Path("assets") / path.relative_to(ASSETS_DIR)).as_posix()
        for path in photo_dir.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    }
    for missing in sorted(referenced_photos - existing):
        errors.append(f"referenced photo does not exist: {missing}")


def _validate_rendered_html(html: str, errors: list[str]) -> None:
    parser = _HtmlCollector()
    parser.feed(html)
    ids = {attrs["id"] for _, attrs in parser.elements if attrs.get("id")}
    metadata = {
        attrs.get("property") or attrs.get("name"): attrs.get("content", "")
        for tag, attrs in parser.elements
        if tag == "meta" and (attrs.get("property") or attrs.get("name"))
    }
    canonical_urls = [attrs.get("href", "") for tag, attrs in parser.elements if tag == "link" and attrs.get("rel") == "canonical"]
    for key in ("og:url", "og:image", "twitter:card", "twitter:image"):
        if not metadata.get(key):
            errors.append(f"rendered page is missing required sharing metadata: {key}")
    if not metadata.get("og:image", "").startswith("https://"):
        errors.append("rendered og:image must use an absolute https URL")
    if len(canonical_urls) != 1 or not canonical_urls[0].startswith("https://"):
        errors.append("rendered page must contain one absolute canonical URL")
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
    source_path = ASSETS_DIR / path_part.removeprefix("assets/") if path_part.startswith("assets/") else ROOT / path_part
    if path_part and not source_path.exists():
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


def _report(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)
