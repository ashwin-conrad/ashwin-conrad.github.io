"""Translate canonical resume JSON into public and working Word controls.

The public projection uses the documented ID-based selection policy in
``resume.json``. The working projection adds a trailing bullet to every mapped
entry and one blank add-new entry per repeatable section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


class ResumeMappingError(RuntimeError):
    """Raised when canonical resume content cannot fill its Word controls."""


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

DEFAULT_ENTRY_BULLET_CAPACITY = {
    "EXP": 4,
    "LEAD": 1,
    "COMM": 1,
    "RECOG": 1,
    "PROJECT": 4,
}


@dataclass
class ResumeRecord:
    """Values sent to the DOCX renderer and their canonical-data origins."""

    values: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    optional_tags: set[str] = field(default_factory=set)
    blank_entries: set[str] = field(default_factory=set)

    def add(self, tag: str, value: object, source: str, *, optional: bool = False) -> None:
        self.values[tag] = "" if value is None else str(value).strip()
        self.sources[tag] = source
        if optional:
            self.optional_tags.add(tag)


def build_resume_record(resume: dict[str, Any], *, include_working_blanks: bool = False) -> ResumeRecord:
    """Build a tag-addressed record from independent concise resume content."""

    if not resume:
        raise ResumeMappingError("content/details/resume.json is empty")

    record = ResumeRecord()
    contact = _contact_parts(resume.get("contact", []))

    record.add("CONTACT_NAME", resume.get("name", ""), "resume.name")
    record.add("CONTACT_LOCATION", contact["location"], "resume.contact")
    record.add("PROFILE_SUMMARY", resume.get("headline", ""), "resume.headline")
    record.add("CONTACT_PHONE", contact["phone"], "resume.contact")
    record.add("CONTACT_EMAIL", contact["email"], "resume.contact")
    record.add("CONTACT_WEBSITE", contact["website"], "resume.contact")

    experience_ids, leadership_ids, community_ids, recognition_ids, project_ids = word_slot_order(resume)
    items_by_id = _resume_items_by_id(resume)
    education_ids = education_slot_order(resume)
    _ensure_known_ids(items_by_id, education_ids, "education")
    for index, item_id in enumerate(education_ids, start=1):
        _add_education_entry(
            record,
            education_tag_prefix(index),
            items_by_id[item_id],
            f"resume item {item_id}",
            add_blank_bullet=include_working_blanks,
        )
    if include_working_blanks:
        _add_education_entry(
            record,
            education_tag_prefix(len(education_ids) + 1),
            {},
            "new education entry",
            add_blank_bullet=True,
            blank_entry=True,
        )

    _ensure_known_ids(items_by_id, experience_ids, "experience")
    for index, item_id in enumerate(experience_ids, start=1):
        item = items_by_id[item_id]
        _add_entry(record, "EXP", index, item, f"resume item {item_id}", add_blank_bullet=include_working_blanks)
    if include_working_blanks:
        _add_entry(record, "EXP", len(experience_ids) + 1, {}, "new experience entry", bullet_capacity=4, blank_entry=True)

    _ensure_known_ids(items_by_id, leadership_ids, "leadership")
    for index, item_id in enumerate(leadership_ids, start=1):
        _add_entry(record, "LEAD", index, items_by_id[item_id], f"resume item {item_id}", add_blank_bullet=include_working_blanks)
    if include_working_blanks:
        _add_entry(record, "LEAD", len(leadership_ids) + 1, {}, "new leadership entry", bullet_capacity=1, blank_entry=True)

    _ensure_known_ids(items_by_id, community_ids, "community")
    for index, item_id in enumerate(community_ids, start=1):
        _add_entry(record, "COMM", index, items_by_id[item_id], f"resume item {item_id}", add_blank_bullet=include_working_blanks)
    if include_working_blanks:
        _add_entry(record, "COMM", len(community_ids) + 1, {}, "new community entry", bullet_capacity=1, blank_entry=True)

    _ensure_known_ids(items_by_id, recognition_ids, "recognition")
    for index, item_id in enumerate(recognition_ids, start=1):
        _add_entry(record, "RECOG", index, items_by_id[item_id], f"resume item {item_id}", add_blank_bullet=include_working_blanks)
    if include_working_blanks:
        _add_entry(record, "RECOG", len(recognition_ids) + 1, {}, "new recognition entry", bullet_capacity=1, blank_entry=True)

    general_skills = list(resume.get("general_skills", []))[:6]
    if len(general_skills) < 6:
        raise ResumeMappingError("The Word template requires at least six entries in resume.general_skills")
    for index, skill in enumerate(general_skills, start=1):
        record.add(f"GENERAL_SKILL_{index}", skill, f"general_skills[{index - 1}]")

    record.add("PAGE2_NAME", resume.get("name", ""), "resume.name")
    record.add("PAGE2_WEBSITE", contact["website"], "resume.contact")

    _ensure_known_ids(items_by_id, project_ids, "project")
    previous_category = ""
    for index, item_id in enumerate(project_ids, start=1):
        project = items_by_id[item_id]
        category = str(project.get("category", "")).strip()
        record.add(
            f"PROJECT{index}_CATEGORY",
            category if category != previous_category else "",
            f"resume item {item_id}.category",
            optional=category == previous_category,
        )
        _add_entry(record, "PROJECT", index, project, f"resume item {item_id}", add_blank_bullet=include_working_blanks)
        previous_category = category
    if include_working_blanks:
        record.add(
            f"PROJECT{len(project_ids) + 1}_CATEGORY",
            "",
            "new project entry.category",
            optional=True,
        )
        _add_entry(record, "PROJECT", len(project_ids) + 1, {}, "new project entry", bullet_capacity=4, blank_entry=True)

    skill_sources = _skill_sources(resume)
    for value_tag, keywords in TECHNICAL_SKILL_RULES:
        record.add(value_tag, _select_skill_text(skill_sources, keywords), "resume skills and project tools")
    record.add(
        "TECH_FABRICATION",
        _select_skill_text(skill_sources, ("fabrication", "panel assembly", "mechanical prototyping", "engineering drawings")),
        "resume skills",
    )

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
                if isinstance(item, dict) and _is_included(item) and item.get("id"):
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
                first = next((item for item in block["items"] if isinstance(item, dict) and _is_included(item)), None)
                if first is not None:
                    return first
    raise ResumeMappingError(f"Could not find a {heading!r} resume section item")


def _list_items(resume: dict[str, Any], heading: str) -> list[str]:
    for page in resume.get("pages", []):
        for block in page.get("blocks", []):
            if str(block.get("heading", "")).casefold() != heading.casefold():
                continue
            values = []
            for item in block.get("items", []):
                if isinstance(item, dict) and not _is_included(item):
                    continue
                value = item.get("text", "") if isinstance(item, dict) else item
                if str(value).strip():
                    values.append(str(value).strip())
            return values
    return []


def _add_entry(
    record: ResumeRecord,
    prefix: str,
    index: int,
    item: dict[str, Any],
    source: str,
    *,
    add_blank_bullet: bool = False,
    bullet_capacity: int | None = None,
    blank_entry: bool = False,
) -> None:
    bullets = list(item.get("bullets", []))
    capacity = bullet_capacity if bullet_capacity is not None else len(bullets)
    if add_blank_bullet:
        capacity = max(capacity + 1, DEFAULT_ENTRY_BULLET_CAPACITY[prefix])
    entry_key = f"{prefix}{index}"
    record.add(f"{entry_key}_TITLE", item.get("role", ""), source, optional=blank_entry)
    record.add(
        f"{entry_key}_META",
        _join_nonempty((item.get("organization", ""), item.get("location", "")), " - "),
        source,
        optional=blank_entry or prefix == "RECOG",
    )
    record.add(
        f"{entry_key}_DATES",
        item.get("dates", ""),
        source,
        optional=blank_entry or prefix in {"COMM", "RECOG"},
    )
    for bullet_index in range(1, capacity + 1):
        record.add(
            f"{entry_key}_BULLET{bullet_index}",
            bullets[bullet_index - 1] if bullet_index <= len(bullets) else "",
            f"{source}.bullets[{bullet_index - 1}]",
            optional=blank_entry or bullet_index > len(bullets),
        )
    if blank_entry:
        record.blank_entries.add(entry_key)


def _add_education_entry(
    record: ResumeRecord,
    tag_prefix: str,
    item: dict[str, Any],
    source: str,
    *,
    add_blank_bullet: bool = False,
    blank_entry: bool = False,
) -> None:
    bullets = list(item.get("bullets", []))
    record.add(f"{tag_prefix}_INSTITUTION", item.get("organization", ""), source, optional=blank_entry)
    record.add(
        f"{tag_prefix}_DEGREE",
        _join_nonempty((item.get("role", ""), item.get("location", "")), " - "),
        source,
        optional=blank_entry,
    )
    record.add(f"{tag_prefix}_DATES", item.get("dates", ""), source, optional=blank_entry)
    capacity = len(bullets) + int(add_blank_bullet)
    for bullet_index in range(1, capacity + 1):
        record.add(
            f"{tag_prefix}_BULLET{bullet_index}",
            bullets[bullet_index - 1] if bullet_index <= len(bullets) else "",
            f"{source}.bullets[{bullet_index - 1}]",
            optional=blank_entry or bullet_index > len(bullets),
        )
    if blank_entry:
        record.blank_entries.add(tag_prefix)


def _bullets_as_text(item: dict[str, Any]) -> str:
    return " ".join(str(bullet).strip() for bullet in item.get("bullets", []) if str(bullet).strip())


def _skill_sources(resume: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for page in resume.get("pages", []):
        for block in page.get("blocks", []):
            for group in block.get("groups", []):
                sources.extend(str(item).strip() for item in group.get("items", []) if str(item).strip())
            for item in block.get("items", []):
                if not isinstance(item, dict) or not _is_included(item) or not item.get("location"):
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


def word_slot_order(
    resume: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Read the Word layout selections from neutral resume metadata."""

    meta = resume.get("_meta")
    slots = meta.get("word_slot_order") if isinstance(meta, dict) else None
    if not isinstance(slots, dict):
        raise ResumeMappingError("resume._meta.word_slot_order must configure the fixed Word layout")
    return (
        _slot_ids(slots.get("experience"), "experience"),
        _slot_ids(slots.get("leadership"), "leadership"),
        _slot_ids(slots.get("community"), "community"),
        _slot_ids(slots.get("recognition"), "recognition"),
        _slot_ids(slots.get("projects"), "projects"),
    )


def education_slot_order(resume: dict[str, Any]) -> tuple[str, ...]:
    """Read the education records assigned to the Word layout."""

    meta = resume.get("_meta")
    slots = meta.get("word_slot_order") if isinstance(meta, dict) else None
    if not isinstance(slots, dict):
        raise ResumeMappingError("resume._meta.word_slot_order must configure the fixed Word layout")
    return _slot_ids(slots.get("education"), "education")


def _slot_ids(value: object, label: str, expected_count: int | None = None) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or (expected_count is not None and len(value) != expected_count)
        or not all(isinstance(item, str) and item for item in value)
    ):
        expectation = f"exactly {expected_count}" if expected_count is not None else "one or more"
        raise ResumeMappingError(
            f"resume._meta.word_slot_order.{label} must contain {expectation} non-empty item IDs"
        )
    return tuple(value)


def education_tag_prefix(index: int) -> str:
    return "EDU" if index == 1 else f"EDU{index}"


def _is_included(item: dict[str, Any]) -> bool:
    include = item.get("include", True)
    if not isinstance(include, bool):
        raise ResumeMappingError("resume item include must be true or false")
    return include
