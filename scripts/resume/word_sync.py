"""Import editable Word resume controls into independent ``resume.json`` content."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .mapper import (
    _resume_items_by_id,
    education_slot_order,
    word_slot_order,
)
from .validation import ALL_RESUME_TAGS, OPTIONAL_TAGS


class WordResumeSyncError(RuntimeError):
    """Raised when an editable Word resume cannot be imported unambiguously."""


def sync_word_values_into_resume(resume_data: dict[str, Any], values: dict[str, str]) -> dict[str, Any]:
    """Return a resume-data copy updated with values entered in Word.

    The retained document intentionally repeats the name and website on page
    two. The page-one header is authoritative, so a normal rebuild refreshes
    any stale repeat field after a user edits only the header. Presentation-only
    controls (technical category labels and the portfolio callout) remain in
    the document and are not copied into website JSON.
    """

    missing = sorted((ALL_RESUME_TAGS - OPTIONAL_TAGS) - set(values))
    if missing:
        raise WordResumeSyncError("Word resume is missing value(s): " + ", ".join(missing))
    values = {**{tag: "" for tag in OPTIONAL_TAGS}, **values}

    resume = deepcopy(resume_data)

    _sync_header(resume, values)
    items = _resume_items_by_id(resume)
    _sync_education(items, education_slot_order(resume), values)
    experience_ids, leadership_ids, community_ids, recognition_ids, project_ids = word_slot_order(resume)
    _sync_entries(items, "EXP", experience_ids, 4, values)
    _sync_entries(items, "LEAD", leadership_ids, 1, values)
    _sync_entries(items, "COMM", community_ids, 1, values)
    _sync_entries(items, "RECOG", recognition_ids, 1, values)
    _sync_general_skills(resume, values)
    _sync_entries(items, "PROJECT", project_ids, 4, values)
    _sync_technical_skills(resume, values)
    return resume


def _sync_header(resume: dict[str, Any], values: dict[str, str]) -> None:
    resume["name"] = values["CONTACT_NAME"]
    resume["headline"] = values["PROFILE_SUMMARY"]
    resume["contact"] = {
        "location": values["CONTACT_LOCATION"],
        "phone": values["CONTACT_PHONE"],
        "email": values["CONTACT_EMAIL"],
        "website": values["CONTACT_WEBSITE"],
    }


def _sync_education(
    items: dict[str, dict[str, Any]], education_ids: tuple[str, str], values: dict[str, str]
) -> None:
    for tag_prefix, item_id in zip(("EDU", "EDU2"), education_ids, strict=True):
        education = _item(items, item_id)
        education["organization"] = values[f"{tag_prefix}_INSTITUTION"]
        education["role"], education["location"] = _split_with_fallback(
            values[f"{tag_prefix}_DEGREE"], education.get("role", ""), education.get("location", "")
        )
        education["dates"] = values[f"{tag_prefix}_DATES"]
        education["bullets"] = [values[f"{tag_prefix}_BULLET1"]]


def _sync_entries(
    items: dict[str, dict[str, Any]], prefix: str, item_ids: tuple[str, ...], bullet_count: int, values: dict[str, str]
) -> None:
    for index, item_id in enumerate(item_ids, start=1):
        item = _item(items, item_id)
        item["organization"], item["location"] = _split_with_fallback(
            values[f"{prefix}{index}_META"], item.get("organization", ""), item.get("location", "")
        )
        item["role"] = values[f"{prefix}{index}_TITLE"]
        item["dates"] = values[f"{prefix}{index}_DATES"]
        item["bullets"] = [values[f"{prefix}{index}_BULLET{bullet_index}"] for bullet_index in range(1, bullet_count + 1)]


def _sync_general_skills(resume: dict[str, Any], values: dict[str, str]) -> None:
    resume["general_skills"] = [values[f"GENERAL_SKILL_{index}"] for index in range(1, 7)]


def _sync_technical_skills(resume: dict[str, Any], values: dict[str, str]) -> None:
    technical = _list_block(resume, "Technical Skills")
    groups = technical.setdefault("groups", [])
    if not groups:
        groups.append({"label": "Engineering", "items": []})
    if not isinstance(groups[0], dict):
        raise WordResumeSyncError("Technical Skills group has an unsupported format")
    groups[0]["items"] = _unique_csv(
        values["TECH_CAD"],
        values["TECH_ELECTRICAL"],
        values["TECH_DATA"],
        values["TECH_ENGINEERING_SOFTWARE"],
    )



def _item(items: dict[str, dict[str, Any]], item_id: str) -> dict[str, Any]:
    try:
        return items[item_id]
    except KeyError as error:
        raise WordResumeSyncError(f"Word resume maps to missing canonical resume item: {item_id}") from error


def _list_block(resume: dict[str, Any], heading: str) -> dict[str, Any]:
    for page in resume.get("pages", []):
        for block in page.get("blocks", []):
            if str(block.get("heading", "")).casefold() == heading.casefold():
                return block
    raise WordResumeSyncError(f"content/details/resume.json is missing its {heading!r} resume block")


def _set_list_item(block: dict[str, Any], index: int, text: str) -> None:
    items = block.setdefault("items", [])
    while len(items) <= index:
        items.append({"text": ""})
    existing = items[index]
    if isinstance(existing, dict):
        existing["text"] = text
    else:
        items[index] = {"text": text}


def _split_with_fallback(value: str, first: object, second: object) -> tuple[str, str]:
    if " - " in value:
        left, right = value.rsplit(" - ", 1)
        return left.strip(), right.strip()
    return value.strip(), str(second).strip()


def _join_title_detail(title: str, detail: str) -> str:
    return f"{title} - {detail}" if title and detail else title or detail


def _nonempty(*items: str) -> list[str]:
    return [item for item in items if item]


def _unique_csv(*values: str) -> list[str]:
    items: list[str] = []
    for value in values:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in items:
                items.append(cleaned)
    return items
