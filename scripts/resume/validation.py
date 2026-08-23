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
ALL_RESUME_TAGS = frozenset(
    {
        "CONTACT_NAME", "CONTACT_LOCATION", "PROFILE_SUMMARY", "CONTACT_PHONE", "CONTACT_EMAIL", "CONTACT_WEBSITE",
        "EDU_INSTITUTION", "EDU_DEGREE", "EDU_DATES",
        "EXP1_COMPANY", "EXP1_TITLE", "EXP1_DATES", "EXP1_BULLET1", "EXP1_BULLET2",
        "EXP2_COMPANY", "EXP2_TITLE", "EXP2_DATES", "EXP2_BULLET1", "EXP2_BULLET2",
        "LEAD1_TITLE", "LEAD1_DETAIL", "COMMUNITY1_TITLE", "COMMUNITY1_DETAIL", "LEAD2_TITLE", "LEAD2_DATES",
        "COMMUNITY2_TITLE", "COMMUNITY2_DETAIL",
        "GENERAL_SKILL_1", "GENERAL_SKILL_2", "GENERAL_SKILL_3", "GENERAL_SKILL_4", "GENERAL_SKILL_5", "GENERAL_SKILL_6",
        "AWARD_1", "AWARD_2", "AWARD_3", "PAGE2_NAME", "PAGE2_WEBSITE",
        "PROJECT1_TITLE", "PROJECT1_CONTEXT", "PROJECT1_TOOLS", "PROJECT1_DATES", "PROJECT1_DESCRIPTION",
        "PROJECT2_TITLE", "PROJECT2_CONTEXT", "PROJECT2_TOOLS", "PROJECT2_DATES", "PROJECT2_DESCRIPTION",
        "PROJECT3_TITLE", "PROJECT3_CONTEXT", "PROJECT3_TOOLS", "PROJECT3_DATES", "PROJECT3_DESCRIPTION",
        "PROJECT4_TITLE", "PROJECT4_CONTEXT", "PROJECT4_TOOLS", "PROJECT4_DATES", "PROJECT4_DESCRIPTION",
        "TECH_CATEGORY_1", "TECH_CAD", "TECH_CATEGORY_2", "TECH_ELECTRICAL", "TECH_CATEGORY_3", "TECH_DATA",
        "TECH_CATEGORY_4", "TECH_ENGINEERING_SOFTWARE", "TECH_CATEGORY_5", "TECH_FABRICATION",
        "PORTFOLIO_CALLOUT", "PORTFOLIO_URL",
    }
)

# These controls are Word-only presentation copy. They stay in the editable
# document because the website does not have a matching structured field.
STATIC_DOCUMENT_TAGS = frozenset(
    {
        "TECH_CATEGORY_1", "TECH_CATEGORY_2", "TECH_CATEGORY_3", "TECH_CATEGORY_4", "TECH_CATEGORY_5",
        "PORTFOLIO_CALLOUT",
    }
)
RENDERED_TAGS = ALL_RESUME_TAGS - STATIC_DOCUMENT_TAGS
OPTIONAL_TAGS = {"COMMUNITY2_TITLE", "COMMUNITY2_DETAIL"}

# These limits are based on the supplied fixed cells and their default text:
# the longest supplied profile is 264 characters, experience bullets 169, and
# project descriptions 187. Values exceeding a documented limit must be edited
# in content/resume.json rather than silently shortened by the renderer.
FIELD_LIMITS: dict[str, int] = {
    "PROFILE_SUMMARY": 300,
    "EXP*_BULLET*": 185,
    "PROJECT*_DESCRIPTION": 260,
    "PROJECT*_TITLE": 55,
    "PROJECT*_TOOLS": 115,
    "GENERAL_SKILL_*": 36,
    "TECH_*": 125,
    "LEAD1_DETAIL": 230,
    "COMMUNITY*_DETAIL": 90,
    "AWARD_*": 55,
    "PORTFOLIO_CALLOUT": 85,
}


class ResumeValidationError(RuntimeError):
    """Base class for an actionable resume validation failure."""


class TemplateValidationError(ResumeValidationError):
    """Raised when the editable Word resume no longer has the required controls."""


class ResumeContentValidationError(ResumeValidationError):
    """Raised when source content cannot safely fit in the Word resume."""


def validate_resume_document(docx_path: Path) -> None:
    """Validate the editable Word document's Content Control inventory."""

    if not docx_path.exists():
        raise TemplateValidationError(
            f"Editable resume document not found: {docx_path}. Restore portfolio/resume.docx before building."
        )
    root = read_document_root(docx_path)
    tags = [control.tag for control in find_content_controls(root) if control.tag]
    validate_tag_inventory(tags, set(ALL_RESUME_TAGS))


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
            f"Resume PDF has {page_count} pages; expected {expected_pages}. Shorten content/resume.json before rebuilding."
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
