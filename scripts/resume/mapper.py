"""Translate the canonical resume JSON into Word content-control values.

The Word template is deliberately fixed to two pages, so its presentation slots
use a documented ID-based selection policy rather than mirroring every resume
item automatically. Content comes from ``content/resume.json``; these constants
only decide which existing stable IDs occupy the fixed slots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


class ResumeMappingError(RuntimeError):
    """Raised when canonical resume content cannot fill the fixed Word layout."""


# The template has room for two professional-experience entries and four
# selected-project entries. Formula EV is intentionally presented as leadership
# on page 1 and as technical project work on page 2.
WORD_EXPERIENCE_ORDER = ("altagas-coop", "spartan-controls-technician")
WORD_LEADERSHIP_EXPERIENCE_ID = "formula-ev-lv"
WORD_PROJECT_ORDER = (
    "heat-exchanger-lifecycle-analysis",
    "inspection-scope-tool",
    "formula-ev-electrical-systems",
    "leather-tool-carrier",
)

TECHNICAL_SKILL_RULES = (
    (
        "TECH_CAD",
        ("solidworks", "autocad", "engineering drawings", "mechanical prototyping", "3d modelling", "2d laser"),
    ),
    (
        "TECH_ELECTRICAL",
        ("low-voltage", "power distribution", "sensor integration", "electrical schematics", "panel assembly", "qa"),
    ),
    (
        "TECH_DATA",
        ("python", "openpyxl", "python-docx", "excel data analysis", "power query", "power bi", "microsoft fabric"),
    ),
    (
        "TECH_ENGINEERING_SOFTWARE",
        ("aspen hysys", "maximo", "jde"),
    ),
)


@dataclass
class ResumeRecord:
    """Values sent to the DOCX renderer and their canonical-data origins."""

    values: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)

    def add(self, tag: str, value: object, source: str) -> None:
        self.values[tag] = "" if value is None else str(value).strip()
        self.sources[tag] = source


def build_resume_record(resume: dict[str, Any]) -> ResumeRecord:
    """Build a tag-addressed record from independent concise resume content."""

    if not resume:
        raise ResumeMappingError("content/resume.json is empty")

    record = ResumeRecord()
    contact = _contact_parts(resume.get("contact", []))

    record.add("CONTACT_NAME", resume.get("name", ""), "resume.name")
    record.add("CONTACT_LOCATION", contact["location"], "resume.contact")
    record.add("PROFILE_SUMMARY", resume.get("headline", ""), "resume.headline")
    record.add("CONTACT_PHONE", contact["phone"], "resume.contact")
    record.add("CONTACT_EMAIL", contact["email"], "resume.contact")
    record.add("CONTACT_WEBSITE", contact["website"], "resume.contact")

    education = _first_section_item(resume, "Education")
    record.add("EDU_INSTITUTION", education.get("organization", ""), "resume.pages[0].Education")
    degree_and_location = _join_nonempty((education.get("role", ""), education.get("location", "")), " - ")
    record.add("EDU_DEGREE", degree_and_location, "resume.pages[0].Education")
    record.add("EDU_DATES", education.get("dates", ""), "resume.pages[0].Education")

    items_by_id = _resume_items_by_id(resume)
    _ensure_known_ids(items_by_id, WORD_EXPERIENCE_ORDER + (WORD_LEADERSHIP_EXPERIENCE_ID,), "experience")
    for index, item_id in enumerate(WORD_EXPERIENCE_ORDER, start=1):
        item = items_by_id[item_id]
        _add_experience(record, index, item, f"resume item {item_id}")

    formula = items_by_id[WORD_LEADERSHIP_EXPERIENCE_ID]
    record.add(
        "LEAD1_TITLE",
        _join_nonempty((formula.get("organization", ""), formula.get("role", "")), " - "),
        f"resume item {WORD_LEADERSHIP_EXPERIENCE_ID}",
    )
    record.add(
        "LEAD1_DETAIL",
        _bullets_as_text(formula),
        f"resume item {WORD_LEADERSHIP_EXPERIENCE_ID}.bullets",
    )

    leadership_items = _list_items(resume, "Leadership")
    if not leadership_items:
        raise ResumeMappingError("The Word template requires one Leadership list item in content/resume.json")
    lead2_title, lead2_dates = _split_trailing_dates(leadership_items[0])
    record.add("LEAD2_TITLE", lead2_title, "resume.pages[0].Leadership[0]")
    record.add("LEAD2_DATES", lead2_dates, "resume.pages[0].Leadership[0]")

    community_items = _list_items(resume, "Community")
    if not community_items:
        raise ResumeMappingError("The Word template requires a Community list item (CYDC Basketball Coach) in content/resume.json")
    community_title, community_detail = _split_title_and_detail(community_items[0])
    record.add("COMMUNITY1_TITLE", community_title, "resume.pages[0].Community[0]")
    record.add("COMMUNITY1_DETAIL", community_detail, "resume.pages[0].Community[0]")
    record.add("COMMUNITY2_TITLE", "", "optional community slot")
    record.add("COMMUNITY2_DETAIL", "", "optional community slot")

    general_skills = list(resume.get("general_skills", []))[:6]
    if len(general_skills) < 6:
        raise ResumeMappingError("The Word template requires at least six entries in resume.general_skills")
    for index, skill in enumerate(general_skills, start=1):
        record.add(f"GENERAL_SKILL_{index}", skill, f"general_skills[{index - 1}]")

    awards = _list_items(resume, "Awards")
    if len(awards) > 3:
        raise ResumeMappingError("The Word template has three award slots; reduce or explicitly remap the Awards list")
    for index in range(1, 4):
        record.add(f"AWARD_{index}", awards[index - 1] if index <= len(awards) else "", f"resume.pages[0].Awards[{index - 1}]")

    record.add("PAGE2_NAME", resume.get("name", ""), "resume.name")
    record.add("PAGE2_WEBSITE", contact["website"], "resume.contact")

    _ensure_known_ids(items_by_id, WORD_PROJECT_ORDER, "project")
    for index, item_id in enumerate(WORD_PROJECT_ORDER, start=1):
        project = items_by_id[item_id]
        _add_project(record, index, project, f"resume item {item_id}")

    skill_sources = _skill_sources(resume)
    for value_tag, keywords in TECHNICAL_SKILL_RULES:
        record.add(value_tag, _select_skill_text(skill_sources, keywords), "resume skills and project tools")
    fabrication = _list_items(resume, "Hands-on Work")
    record.add("TECH_FABRICATION", fabrication[0] if fabrication else "", "resume.pages[0].Hands-on Work")

    record.add("PORTFOLIO_URL", contact["website"], "resume.contact")
    return record


def _contact_parts(contact: object) -> dict[str, str]:
    if isinstance(contact, dict):
        return {key: str(contact.get(key, "")).strip() for key in ("location", "phone", "email", "website")}
    values = [str(value).strip() for value in contact if str(value).strip()] if isinstance(contact, list) else []
    email = next((value for value in values if "@" in value), "")
    phone = next((value for value in values if sum(char.isdigit() for char in value) >= 7), "")
    website = next(
        (value for value in values if value not in {email, phone} and "." in value and " " not in value),
        "",
    )
    location = next((value for value in values if value not in {email, phone, website}), "")
    return {"location": location, "phone": phone, "email": email, "website": website}


def _resume_items_by_id(resume: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for page in resume.get("pages", []):
        for block in page.get("blocks", []):
            for item in block.get("items", []):
                if isinstance(item, dict) and item.get("id"):
                    item_id = str(item["id"])
                    if item_id in items:
                        raise ResumeMappingError(f"Duplicate resume ID found while mapping the Word resume: {item_id}")
                    items[item_id] = item
    return items


def _ensure_known_ids(items_by_id: dict[str, dict[str, Any]], ids: tuple[str, ...], kind: str) -> None:
    missing = [item_id for item_id in ids if item_id not in items_by_id]
    if missing:
        raise ResumeMappingError(f"Word {kind} slot mapping references missing resume ID(s): {', '.join(missing)}")


def _first_section_item(resume: dict[str, Any], heading: str) -> dict[str, Any]:
    for page in resume.get("pages", []):
        for block in page.get("blocks", []):
            if str(block.get("heading", "")).casefold() == heading.casefold() and block.get("items"):
                first = block["items"][0]
                if isinstance(first, dict):
                    return first
    raise ResumeMappingError(f"Could not find a {heading!r} resume section item")


def _list_items(resume: dict[str, Any], heading: str) -> list[str]:
    for page in resume.get("pages", []):
        for block in page.get("blocks", []):
            if str(block.get("heading", "")).casefold() != heading.casefold():
                continue
            values = []
            for item in block.get("items", []):
                value = item.get("text", "") if isinstance(item, dict) else item
                if str(value).strip():
                    values.append(str(value).strip())
            return values
    return []


def _add_experience(record: ResumeRecord, index: int, item: dict[str, Any], source: str) -> None:
    bullets = list(item.get("bullets", []))
    if len(bullets) > 2:
        raise ResumeMappingError(f"{source} has {len(bullets)} bullets; the Word experience slot supports two")
    record.add(f"EXP{index}_COMPANY", _join_nonempty((item.get("organization", ""), item.get("location", "")), " - "), source)
    record.add(f"EXP{index}_TITLE", item.get("role", ""), source)
    record.add(f"EXP{index}_DATES", item.get("dates", ""), source)
    for bullet_index in range(1, 3):
        record.add(
            f"EXP{index}_BULLET{bullet_index}",
            bullets[bullet_index - 1] if bullet_index <= len(bullets) else "",
            f"{source}.bullets[{bullet_index - 1}]",
        )


def _add_project(record: ResumeRecord, index: int, item: dict[str, Any], source: str) -> None:
    record.add(f"PROJECT{index}_TITLE", item.get("role", ""), source)
    record.add(f"PROJECT{index}_CONTEXT", item.get("organization", ""), source)
    record.add(f"PROJECT{index}_TOOLS", item.get("location", ""), source)
    record.add(f"PROJECT{index}_DATES", item.get("dates", ""), source)
    record.add(f"PROJECT{index}_DESCRIPTION", _bullets_as_text(item), f"{source}.bullets")


def _bullets_as_text(item: dict[str, Any]) -> str:
    return " ".join(str(bullet).strip() for bullet in item.get("bullets", []) if str(bullet).strip())


def _skill_sources(resume: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for page in resume.get("pages", []):
        for block in page.get("blocks", []):
            for group in block.get("groups", []):
                sources.extend(str(item).strip() for item in group.get("items", []) if str(item).strip())
            for item in block.get("items", []):
                if not isinstance(item, dict) or not item.get("location"):
                    continue
                location = str(item["location"]).strip()
                # Project tool fields supplement the data/automation category
                # (for example, openpyxl and python-docx) without repeating
                # vehicle and panel skills already present in the master skills
                # list.
                if any(token in location.casefold() for token in ("python", "openpyxl", "power bi", "power query", "fabric")):
                    sources.append(location)
    pieces: list[str] = []
    for source in sources:
        pieces.extend(piece.strip() for piece in source.split(",") if piece.strip())
    return pieces


def _select_skill_text(sources: list[str], keywords: tuple[str, ...]) -> str:
    selected: list[str] = []
    for source in sources:
        if any(keyword in source.casefold() for keyword in keywords) and source not in selected:
            selected.append(source)
    return ", ".join(selected)


def _split_trailing_dates(value: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)(?:,\s*)(\d{4}\s*[-–]\s*\d{4}|\d{4}\s*[-–]\s*Present)$", value)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return value, ""


def _split_title_and_detail(value: str) -> tuple[str, str]:
    if " - " in value:
        title, detail = value.split(" - ", 1)
        return title.strip(), detail.strip()
    if ":" in value:
        title, detail = value.split(":", 1)
        return title.strip(), detail.strip()
    return value.strip(), ""


def _join_nonempty(parts: tuple[object, ...], separator: str) -> str:
    return separator.join(str(part).strip() for part in parts if str(part).strip())
