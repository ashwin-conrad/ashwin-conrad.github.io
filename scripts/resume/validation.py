"""Structural, content-capacity, and PDF page-count validation for resumes."""

from __future__ import annotations

from collections import Counter
import fnmatch
from pathlib import Path

from pypdf import PdfReader

from .mapper import ResumeRecord
from .word_renderer import find_content_controls, read_document_root


# This is the public control contract for the retained editable document. It
# replaces the former, duplicate JSON field map. Changing the layout in Word is
# fine; removing, renaming, or duplicating one of these controls is not.
def _entry_tags(prefix: str, count: int, bullets: int) -> set[str]:
    return {
        tag
        for index in range(1, count + 1)
        for tag in (
            f"{prefix}{index}_TITLE",
            f"{prefix}{index}_META",
            f"{prefix}{index}_DATES",
            *(f"{prefix}{index}_BULLET{bullet}" for bullet in range(1, bullets + 1)),
        )
    }


ALL_RESUME_TAGS = frozenset(
    {
        "CONTACT_NAME", "CONTACT_LOCATION", "PROFILE_SUMMARY", "CONTACT_PHONE", "CONTACT_EMAIL", "CONTACT_WEBSITE",
        "EDU_INSTITUTION", "EDU_DEGREE", "EDU_DATES",
        "EDU2_INSTITUTION", "EDU2_DEGREE", "EDU2_DATES",
        "EDU_BULLET1", "EDU2_BULLET1",
        *(f"GENERAL_SKILL_{index}" for index in range(1, 7)),
        "PAGE2_NAME", "PAGE2_WEBSITE",
        "TECH_CAD", "TECH_ELECTRICAL", "TECH_DATA", "TECH_ENGINEERING_SOFTWARE", "TECH_FABRICATION",
        "PORTFOLIO_URL",
    }
    | _entry_tags("EXP", 2, 4)
    | _entry_tags("LEAD", 2, 1)
    | _entry_tags("COMM", 1, 1)
    | _entry_tags("RECOG", 3, 1)
    | _entry_tags("PROJECT", 4, 4)
)

# These controls are Word-only presentation copy. They stay in the editable
# document because the website does not have a matching structured field.
STATIC_DOCUMENT_TAGS = frozenset()
RENDERED_TAGS = ALL_RESUME_TAGS - STATIC_DOCUMENT_TAGS
OPTIONAL_TAGS = {
    "COMM1_DATES",
    "RECOG1_META", "RECOG2_META", "RECOG3_META",
}

# These limits are based on the supplied fixed cells and their default text:
# the longest supplied profile is 264 characters, experience bullets 169, and
# project descriptions 187. Values exceeding a documented limit must be edited
# in content/details/resume.json rather than silently shortened by the renderer.
FIELD_LIMITS: dict[str, int] = {
    "PROFILE_SUMMARY": 300,
    "EXP*_BULLET*": 165,
    "PROJECT*_BULLET*": 165,
    "PROJECT*_TITLE": 65,
    "PROJECT*_META": 115,
    "GENERAL_SKILL_*": 36,
    "TECH_*": 125,
    "LEAD*_BULLET1": 185,
    "EDU*_BULLET1": 260,
    "COMM*_BULLET1": 110,
    "RECOG*_BULLET1": 110,
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
    validate_tag_inventory(tags, expected_tags or set(ALL_RESUME_TAGS))


def validate_record(record: ResumeRecord) -> None:
    """Validate generated values and fixed-layout capacity limits."""

    errors: list[str] = []
    for tag in sorted(RENDERED_TAGS):
        if tag not in record.values:
            errors.append(f"No mapped value for required Content Control tag: {tag}")
            continue
        value = record.values[tag]
        if not value and tag not in OPTIONAL_TAGS:
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
