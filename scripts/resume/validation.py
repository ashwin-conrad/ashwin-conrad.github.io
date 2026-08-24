"""Structural, content-capacity, and PDF page-count validation for resumes."""

from __future__ import annotations

from collections import Counter
import fnmatch
from pathlib import Path
import re

from pypdf import PdfReader

from .mapper import ResumeRecord
from .word_renderer import control_text, find_content_controls, read_document_root


_BULLET_TAG_PATTERN = re.compile(r"^(EDU\d*|(?:EXP|LEAD|COMM|RECOG|PROJECT)\d+)_BULLET(\d+)$")


# These limits are based on the supplied fixed cells and their default text:
# the longest supplied profile is 264 characters, experience bullets 169, and
# project descriptions 187. Values exceeding a documented limit must be edited
# in content/details/resume.json rather than silently shortened by the renderer.
FIELD_LIMITS: dict[str, int] = {
    "PROFILE_SUMMARY": 300,
    "EXP*_BULLET*": 165,
    "PROJECT*_BULLET*": 165,
    "PROJECT*_TITLE": 90,
    "PROJECT*_CATEGORY": 40,
    "PROJECT*_META": 115,
    "GENERAL_SKILL_*": 36,
    "TECH_*": 125,
    "LEAD*_BULLET*": 185,
    "EDU*_BULLET*": 260,
    "COMM*_BULLET*": 125,
    "RECOG*_BULLET*": 110,
}


class ResumeValidationError(RuntimeError):
    """Base class for an actionable resume validation failure."""


class TemplateValidationError(ResumeValidationError):
    """Raised when the editable Word resume no longer has the required controls."""


class ResumeContentValidationError(ResumeValidationError):
    """Raised when source content cannot safely fit in the Word resume."""


def validate_resume_document(docx_path: Path, expected_tags: set[str] | None = None) -> None:
    """Validate the editable Word document's Content Control inventory."""

    if not docx_path.exists():
        raise TemplateValidationError(
            f"Editable resume document not found: {docx_path}. Restore portfolio/resume.docx before building."
        )
    root = read_document_root(docx_path)
    tags = [control.tag for control in find_content_controls(root) if control.tag]
    validate_tag_inventory(tags, expected_tags if expected_tags is not None else set(tags))


def validate_resume_template_capacity(
    docx_path: Path, *, required_tags: set[str], allowed_tags: set[str]
) -> set[str]:
    """Validate a working template whose blank capacity may lag one sync cycle.

    A Word-to-JSON sync compacts empty bullet controls out of canonical JSON.
    The source document still contains those controls until the next working
    copy is generated, so accept only contiguous, trailing, and empty surplus
    bullet controls from otherwise known entries.
    """

    if not docx_path.exists():
        raise TemplateValidationError(f"Editable resume document not found: {docx_path}")
    root = read_document_root(docx_path)
    controls = [control for control in find_content_controls(root) if control.tag]
    tags = [control.tag for control in controls]
    counts = Counter(tags)
    errors = [f"Duplicate Content Control tag: {tag} ({count} occurrences)" for tag, count in sorted(counts.items()) if count > 1]
    actual = set(tags)
    stale_blank_bullets = _stale_blank_bullet_tags(controls, allowed_tags)
    errors.extend(f"Missing Content Control tag: {tag}" for tag in sorted(required_tags - actual))
    errors.extend(
        f"Unexpected Content Control tag: {tag}"
        for tag in sorted(actual - allowed_tags - stale_blank_bullets)
    )
    if errors:
        raise TemplateValidationError("Resume template validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    return actual


def _stale_blank_bullet_tags(controls: list, allowed_tags: set[str]) -> set[str]:
    """Return safe bullet capacity left behind after Word deletes content."""

    allowed_by_entry = _bullet_indices_by_entry(allowed_tags)
    actual_by_entry = _bullet_indices_by_entry(control.tag for control in controls)
    blank_tags = {
        control.tag
        for control in controls
        if not control_text(control.element).strip()
    }
    stale: set[str] = set()
    for entry_key, actual_indices in actual_by_entry.items():
        allowed_indices = allowed_by_entry.get(entry_key, set())
        if not allowed_indices or actual_indices != set(range(1, max(actual_indices) + 1)):
            continue
        allowed_max = max(allowed_indices)
        for index in actual_indices:
            tag = f"{entry_key}_BULLET{index}"
            if index > allowed_max and tag in blank_tags:
                stale.add(tag)
    return stale


def _bullet_indices_by_entry(tags) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for tag in tags:
        match = _BULLET_TAG_PATTERN.fullmatch(tag)
        if match:
            result.setdefault(match.group(1), set()).add(int(match.group(2)))
    return result


def validate_record(record: ResumeRecord) -> None:
    """Validate generated values and fixed-layout capacity limits."""

    errors: list[str] = []
    for tag in sorted(record.values):
        value = record.values[tag]
        if not value and tag not in record.optional_tags:
            errors.append(f"Required resume field is blank: {tag} ({record.sources.get(tag, 'unknown source')})")
        limit = _field_limit(tag)
        if value and limit is not None and len(value) > limit:
            errors.append(
                f"{record.sources.get(tag, tag)}\n  tag: {tag}\n  {len(value)} characters\n  Recommended maximum: {limit}"
            )
    if errors:
        raise ResumeContentValidationError("Resume content validation failed:\n" + "\n".join(f"- {error}" for error in errors))


def validate_pdf_page_count(pdf_path: Path, expected_pages: int = 2) -> None:
    """Fail explicitly if the generated PDF no longer fits the two-page layout."""

    try:
        page_count = len(PdfReader(str(pdf_path)).pages)
    except Exception as error:  # pragma: no cover - converter-specific failures
        raise ResumeValidationError(f"Could not read generated resume PDF {pdf_path}: {error}") from error
    if page_count != expected_pages:
        raise ResumeContentValidationError(
            f"Resume PDF has {page_count} pages; expected {expected_pages}. Shorten content/details/resume.json before rebuilding."
        )


def validate_tag_inventory(tags: list[str], expected_tags: set[str]) -> None:
    """Raise clear diagnostics for missing, duplicate, and unknown controls."""

    counts = Counter(tags)
    errors = [f"Missing Content Control tag: {tag}" for tag in sorted(expected_tags - set(tags))]
    errors.extend(f"Duplicate Content Control tag: {tag} ({count} occurrences)" for tag, count in sorted(counts.items()) if count > 1)
    errors.extend(f"Unexpected Content Control tag: {tag}" for tag in sorted(set(tags) - expected_tags))
    if errors:
        raise TemplateValidationError("Resume template validation failed:\n" + "\n".join(f"- {error}" for error in errors))


def _field_limit(tag: str) -> int | None:
    for pattern, limit in FIELD_LIMITS.items():
        if fnmatch.fnmatchcase(tag, pattern):
            return limit
    return None
