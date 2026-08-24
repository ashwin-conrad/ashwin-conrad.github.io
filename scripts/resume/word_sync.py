"""Import editable Word resume controls into independent ``resume.json`` content."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .mapper import (
    _resume_items_by_id,
    build_resume_record,
    education_slot_order,
    education_tag_prefix,
    word_slot_order,
)


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

    canonical_record = build_resume_record(resume_data)
    missing = sorted((set(canonical_record.values) - canonical_record.optional_tags) - set(values))
    if missing:
        raise WordResumeSyncError("Word resume is missing value(s): " + ", ".join(missing))
    working_record = build_resume_record(resume_data, include_working_blanks=True)
    values = {**{tag: "" for tag in working_record.values}, **values}

    resume = deepcopy(resume_data)

    _sync_header(resume, values)
    items = _resume_items_by_id(resume)
    _sync_education(items, education_slot_order(resume), values)
    experience_ids, leadership_ids, community_ids, recognition_ids, project_ids = word_slot_order(resume)
    _sync_entries(items, "EXP", experience_ids, values)
    _sync_entries(items, "LEAD", leadership_ids, values)
    _sync_entries(items, "COMM", community_ids, values)
    _sync_entries(items, "RECOG", recognition_ids, values)
    _sync_general_skills(resume, values)
    _sync_entries(items, "PROJECT", project_ids, values)
    _sync_new_education(resume, len(education_slot_order(resume)) + 1, values)
    _sync_new_entry(resume, "experience", "Experience", "EXP", len(experience_ids) + 1, values)
    _sync_new_entry(resume, "leadership", "Leadership", "LEAD", len(leadership_ids) + 1, values)
    _sync_new_entry(resume, "community", "Community Involvement", "COMM", len(community_ids) + 1, values)
    _sync_new_entry(resume, "recognition", "Recognition", "RECOG", len(recognition_ids) + 1, values)
    _sync_new_entry(resume, "projects", "Project Portfolio", "PROJECT", len(project_ids) + 1, values)
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
    items: dict[str, dict[str, Any]], education_ids: tuple[str, ...], values: dict[str, str]
) -> None:
    for index, item_id in enumerate(education_ids, start=1):
        tag_prefix = education_tag_prefix(index)
        education = _item(items, item_id)
        education["organization"] = values[f"{tag_prefix}_INSTITUTION"]
        education["role"], education["location"] = _split_with_fallback(
            values[f"{tag_prefix}_DEGREE"], education.get("role", ""), education.get("location", "")
        )
        education["dates"] = values[f"{tag_prefix}_DATES"]
        education["bullets"] = _control_bullets(values, tag_prefix)


def _sync_entries(
    items: dict[str, dict[str, Any]], prefix: str, item_ids: tuple[str, ...], values: dict[str, str]
) -> None:
    for index, item_id in enumerate(item_ids, start=1):
        item = _item(items, item_id)
        item["organization"], item["location"] = _split_with_fallback(
            values[f"{prefix}{index}_META"], item.get("organization", ""), item.get("location", "")
        )
        item["role"] = values[f"{prefix}{index}_TITLE"]
        item["dates"] = values[f"{prefix}{index}_DATES"]
        item["bullets"] = _control_bullets(values, f"{prefix}{index}")


def _sync_new_education(resume: dict[str, Any], index: int, values: dict[str, str]) -> None:
    entry_key = education_tag_prefix(index)
    entry_values = {
        "organization": values[f"{entry_key}_INSTITUTION"],
        "degree": values[f"{entry_key}_DEGREE"],
        "dates": values[f"{entry_key}_DATES"],
        "bullets": _control_bullets(values, entry_key),
    }
    if not _has_new_entry_value(entry_values):
        return
    _require_new_fields("Education", entry_values, ("organization", "degree", "dates"))
    role, location = _split_with_fallback(entry_values["degree"], "", "")
    item_id = _next_item_id(resume, "education")
    _append_new_item(
        resume,
        "education",
        "Education",
        {
            "id": item_id,
            "include": True,
            "role": role,
            "organization": entry_values["organization"],
            "location": location,
            "dates": entry_values["dates"],
            "bullets": entry_values["bullets"],
        },
    )


def _sync_new_entry(
    resume: dict[str, Any], slot_key: str, heading: str, prefix: str, index: int, values: dict[str, str]
) -> None:
    entry_key = f"{prefix}{index}"
    entry_values = {
        "title": values[f"{entry_key}_TITLE"],
        "meta": values[f"{entry_key}_META"],
        "dates": values[f"{entry_key}_DATES"],
        "bullets": _control_bullets(values, entry_key),
    }
    if not _has_new_entry_value(entry_values):
        return
    required = ("title",)
    if prefix in {"EXP", "LEAD", "PROJECT"}:
        required = ("title", "meta", "dates")
    elif prefix == "COMM":
        required = ("title", "meta")
    elif prefix == "RECOG":
        required = ("title", "dates")
    _require_new_fields(heading, entry_values, required)
    organization, location = _split_with_fallback(entry_values["meta"], "", "")
    id_prefix = "project" if slot_key == "projects" else slot_key
    item_id = _next_item_id(resume, id_prefix)
    _append_new_item(
        resume,
        slot_key,
        heading,
        {
            "id": item_id,
            "include": True,
            "role": entry_values["title"],
            "organization": organization,
            "location": location,
            "dates": entry_values["dates"],
            "bullets": entry_values["bullets"],
        },
    )


def _append_new_item(
    resume: dict[str, Any], slot_key: str, heading: str, item: dict[str, Any]
) -> None:
    block = _list_block(resume, heading)
    block.setdefault("items", []).append(item)
    meta = resume.setdefault("_meta", {})
    slots = meta.setdefault("word_slot_order", {}) if isinstance(meta, dict) else None
    if not isinstance(slots, dict) or not isinstance(slots.get(slot_key), list):
        raise WordResumeSyncError(f"resume._meta.word_slot_order.{slot_key} must be a list")
    slots[slot_key].append(item["id"])


def _next_item_id(resume: dict[str, Any], prefix: str) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    numbers = [
        int(match.group(1))
        for page in resume.get("pages", [])
        for block in page.get("blocks", [])
        for item in block.get("items", [])
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and (match := pattern.fullmatch(item["id"]))
    ]
    return f"{prefix}_{max(numbers, default=0) + 1}"


def _control_bullets(values: dict[str, str], entry_key: str) -> list[str]:
    pattern = re.compile(rf"^{re.escape(entry_key)}_BULLET(\d+)$")
    indexed = sorted(
        (int(match.group(1)), value.strip())
        for tag, value in values.items()
        if (match := pattern.fullmatch(tag))
    )
    return [value for _, value in indexed if value]


def _has_new_entry_value(values: dict[str, Any]) -> bool:
    return any(value if not isinstance(value, list) else bool(value) for value in values.values())


def _require_new_fields(heading: str, values: dict[str, Any], required: tuple[str, ...]) -> None:
    missing = [field for field in required if not str(values.get(field, "")).strip()]
    if missing:
        raise WordResumeSyncError(f"New {heading} entry is missing: {', '.join(missing)}")


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
