"""Import editable Word resume controls into independent ``resume.json`` content."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .mapper import (
    WORD_EXPERIENCE_ORDER,
    WORD_LEADERSHIP_EXPERIENCE_ID,
    WORD_PROJECT_ORDER,
    _first_section_item,
    _resume_items_by_id,
)
from .validation import ALL_RESUME_TAGS


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

    missing = sorted(ALL_RESUME_TAGS - set(values))
    if missing:
        raise WordResumeSyncError("Word resume is missing value(s): " + ", ".join(missing))

    resume = deepcopy(resume_data)

    _sync_header(resume, values)
    _sync_education(resume, values)
    items = _resume_items_by_id(resume)
    _sync_experiences(items, values)
    _sync_leadership(resume, items, values)
    _sync_community(resume, values)
    _sync_general_skills(resume, values)
    _sync_awards(resume, values)
    _sync_projects(items, values)
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


def _sync_education(resume: dict[str, Any], values: dict[str, str]) -> None:
    education = _first_section_item(resume, "Education")
    education["organization"] = values["EDU_INSTITUTION"]
    education["role"], education["location"] = _split_with_fallback(
        values["EDU_DEGREE"], education.get("role", ""), education.get("location", "")
    )
    education["dates"] = values["EDU_DATES"]


def _sync_experiences(items: dict[str, dict[str, Any]], values: dict[str, str]) -> None:
    for index, item_id in enumerate(WORD_EXPERIENCE_ORDER, start=1):
        item = _item(items, item_id)
        item["organization"], item["location"] = _split_with_fallback(
            values[f"EXP{index}_COMPANY"], item.get("organization", ""), item.get("location", "")
        )
        item["role"] = values[f"EXP{index}_TITLE"]
        item["dates"] = values[f"EXP{index}_DATES"]
        item["bullets"] = _nonempty(values[f"EXP{index}_BULLET1"], values[f"EXP{index}_BULLET2"])


def _sync_leadership(resume: dict[str, Any], items: dict[str, dict[str, Any]], values: dict[str, str]) -> None:
    formula = _item(items, WORD_LEADERSHIP_EXPERIENCE_ID)
    formula["organization"], formula["role"] = _split_with_fallback(
        values["LEAD1_TITLE"], formula.get("organization", ""), formula.get("role", "")
    )
    formula["bullets"] = _nonempty(values["LEAD1_DETAIL"])

    leadership = _list_block(resume, "Leadership")
    title = values["LEAD2_TITLE"]
    dates = values["LEAD2_DATES"]
    _set_list_item(leadership, 0, f"{title}, {dates}" if dates else title)


def _sync_community(resume: dict[str, Any], values: dict[str, str]) -> None:
    community = _list_block(resume, "Community")
    _set_list_item(community, 0, _join_title_detail(values["COMMUNITY1_TITLE"], values["COMMUNITY1_DETAIL"]))
    optional = _join_title_detail(values["COMMUNITY2_TITLE"], values["COMMUNITY2_DETAIL"])
    if optional:
        _set_list_item(community, 1, optional)
    elif len(community.get("items", [])) > 1:
        del community["items"][1:]


def _sync_general_skills(resume: dict[str, Any], values: dict[str, str]) -> None:
    resume["general_skills"] = [values[f"GENERAL_SKILL_{index}"] for index in range(1, 7)]


def _sync_awards(resume: dict[str, Any], values: dict[str, str]) -> None:
    awards = _list_block(resume, "Awards")
    awards["items"] = [{"text": value} for value in _nonempty(*(values[f"AWARD_{index}"] for index in range(1, 4)))]


def _sync_projects(items: dict[str, dict[str, Any]], values: dict[str, str]) -> None:
    for index, item_id in enumerate(WORD_PROJECT_ORDER, start=1):
        project = _item(items, item_id)
        project["role"] = values[f"PROJECT{index}_TITLE"]
        project["organization"] = values[f"PROJECT{index}_CONTEXT"]
        project["location"] = values[f"PROJECT{index}_TOOLS"]
        project["dates"] = values[f"PROJECT{index}_DATES"]
        project["bullets"] = _nonempty(values[f"PROJECT{index}_DESCRIPTION"])


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

    hands_on = _list_block(resume, "Hands-on Work")
    _set_list_item(hands_on, 0, values["TECH_FABRICATION"])


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
    raise WordResumeSyncError(f"content/resume.json is missing its {heading!r} resume block")


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
