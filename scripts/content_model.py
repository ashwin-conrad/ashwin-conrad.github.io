"""Content loading, safe field references, and relationship validation.

The website has two authored sources: ``site.json`` for site-wide facts and
navigation, and ``details.json`` for the visible page sections.  The resume is
intentionally a third source; it can share selected factual fields through its
own explicit ``_meta.shared_fields`` list without inheriting website prose.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterator

from project_paths import CONTENT_DIR, DETAILS_CONTENT_PATH


class ContentModelError(ValueError):
    """Raised when source data cannot be safely assembled."""


def read_json(path: Path) -> dict[str, Any]:
    data = read_json_value(path)
    if not isinstance(data, dict):
        raise ContentModelError(f"{path.name} must contain a JSON object")
    return data


def read_json_value(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ContentModelError(f"{path.name} is not valid JSON: {error}") from error


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write JSON via a sibling temporary file so interrupted saves are safe."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


@dataclass(frozen=True)
class DetailItem:
    """One item owned by a collection-backed details section."""

    id: str
    relative_path: str
    path: Path


@dataclass(frozen=True)
class DetailSection:
    """A leaf section or an ordered collection of independently stored items."""

    id: str
    path: Path | None = None
    items: tuple[DetailItem, ...] = ()


def load_details_content() -> dict[str, Any]:
    """Load the details manifest and compose its section files for renderers."""

    manifest = read_json(DETAILS_CONTENT_PATH)
    sections = _detail_section_records(manifest)
    portfolio: dict[str, Any] = {}
    for section in sections:
        if section.id in portfolio:
            raise ContentModelError(f"content/details.json contains duplicate section id: {section.id}")
        if section.path:
            value = read_json_value(section.path)
            if not isinstance(value, (dict, list)):
                raise ContentModelError(f"{section.path.name} must contain a JSON object or array")
            portfolio[section.id] = value
            continue

        values: list[dict[str, Any]] = []
        for item in section.items:
            value = read_json_value(item.path)
            if not isinstance(value, dict):
                raise ContentModelError(f"{item.path.name} must contain a JSON object")
            if value.get("id") != item.id:
                raise ContentModelError(
                    f"{item.path.name} has id {value.get('id')!r}; expected manifest id {item.id!r}"
                )
            values.append(value)
        portfolio[section.id] = values
    return {"portfolio": portfolio}


def detail_source_paths() -> list[Path]:
    """Return the manifest and every file it currently owns, in stable order."""

    manifest = read_json(DETAILS_CONTENT_PATH)
    paths = [DETAILS_CONTENT_PATH]
    for section in _detail_section_records(manifest):
        if section.path:
            paths.append(section.path)
        paths.extend(item.path for item in section.items)
    return paths


def write_details_content(details_data: dict[str, Any]) -> None:
    """Persist a composed details object back to its existing section files."""

    portfolio = details_data.get("portfolio")
    if not isinstance(portfolio, dict):
        raise ContentModelError("details.portfolio must be an object")
    manifest = read_json(DETAILS_CONTENT_PATH)
    sections = _detail_section_records(manifest)
    expected_ids = {section.id for section in sections}
    supplied_ids = set(portfolio)
    if supplied_ids != expected_ids:
        missing = sorted(expected_ids - supplied_ids)
        extra = sorted(supplied_ids - expected_ids)
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if extra:
            parts.append("unexpected " + ", ".join(extra))
        raise ContentModelError("Details section manifest mismatch: " + "; ".join(parts))
    manifest_changed = False
    for section in sections:
        value = portfolio[section.id]
        if section.path:
            if not isinstance(value, (dict, list)):
                raise ContentModelError(f"details section {section.id!r} must be an object or list")
            write_json_atomic(section.path, value)
            continue
        manifest_changed = _write_collection_section(manifest, section, value) or manifest_changed
    if manifest_changed:
        write_json_atomic(DETAILS_CONTENT_PATH, manifest)


def _write_collection_section(manifest: dict[str, Any], section: DetailSection, value: Any) -> bool:
    if not isinstance(value, list):
        raise ContentModelError(f"details collection {section.id!r} must be a list")
    known_paths = {item.id: item.relative_path for item in section.items}
    records: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ContentModelError(f"details collection {section.id}[{index}] must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not _SAFE_DETAIL_ID.fullmatch(item_id):
            raise ContentModelError(f"details collection {section.id}[{index}] needs a safe stable id")
        if item_id in seen_ids:
            raise ContentModelError(f"details collection {section.id} contains duplicate id: {item_id}")
        seen_ids.add(item_id)
        relative_path = known_paths.get(item_id, _default_item_path(section.id, item_id))
        write_json_atomic(_details_path(relative_path), item)
        records.append({"id": item_id, "file": relative_path})

    manifest_section = _manifest_section(manifest, section.id)
    if manifest_section.get("items") == records:
        return False
    manifest_section["items"] = records
    return True


def _manifest_section(manifest: dict[str, Any], section_id: str) -> dict[str, Any]:
    sections = manifest.get("portfolio", {}).get("sections")
    if not isinstance(sections, list):  # Already checked by _detail_section_records.
        raise ContentModelError("content/details.json must contain portfolio.sections")
    for section in sections:
        if isinstance(section, dict) and section.get("id") == section_id:
            return section
    raise ContentModelError(f"content/details.json is missing section {section_id!r}")


def _detail_section_records(manifest: dict[str, Any]) -> list[DetailSection]:
    portfolio = manifest.get("portfolio")
    sections = portfolio.get("sections") if isinstance(portfolio, dict) else None
    if not isinstance(sections, list) or not sections:
        raise ContentModelError("content/details.json must contain portfolio.sections")
    records: list[DetailSection] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ContentModelError(f"details manifest section {index} must be an object")
        section_id = section.get("id")
        relative_path = section.get("file")
        item_records = section.get("items")
        if not isinstance(section_id, str) or not section_id:
            raise ContentModelError(f"details manifest section {index} needs an id")
        if isinstance(relative_path, str) and relative_path.endswith(".json") and "items" not in section:
            records.append(DetailSection(section_id, path=_details_path(relative_path)))
            continue
        if "file" in section:
            raise ContentModelError(f"details manifest section {section_id!r} cannot use both file and items")
        if not isinstance(item_records, list) or not item_records:
            raise ContentModelError(f"details manifest collection {section_id!r} needs one or more items")
        items: list[DetailItem] = []
        seen_ids: set[str] = set()
        for item_index, item in enumerate(item_records):
            if not isinstance(item, dict):
                raise ContentModelError(f"details manifest collection {section_id!r} item {item_index} must be an object")
            item_id = item.get("id")
            item_path = item.get("file")
            if not isinstance(item_id, str) or not _SAFE_DETAIL_ID.fullmatch(item_id):
                raise ContentModelError(f"details manifest collection {section_id!r} item {item_index} needs a safe id")
            if item_id in seen_ids:
                raise ContentModelError(f"details manifest collection {section_id!r} contains duplicate id: {item_id}")
            if not isinstance(item_path, str) or not item_path.endswith(".json"):
                raise ContentModelError(f"details manifest collection {section_id!r} item {item_id!r} needs a JSON file path")
            seen_ids.add(item_id)
            items.append(DetailItem(item_id, item_path, _details_path(item_path)))
        records.append(DetailSection(section_id, items=tuple(items)))
    return records


_SAFE_DETAIL_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def _default_item_path(section_id: str, item_id: str) -> str:
    if section_id == "case_studies":
        return f"details/portfolio/projects/{item_id}.json"
    return f"details/portfolio/{section_id.replace('_', '-')}/{item_id}.json"


def _details_path(relative_path: str) -> Path:
    path = (CONTENT_DIR / relative_path).resolve()
    try:
        path.relative_to(CONTENT_DIR.resolve())
    except ValueError as error:
        raise ContentModelError(f"Details file is outside content/: {relative_path}") from error
    return path


def compose_site_content(site_data: dict[str, Any], details_data: dict[str, Any]) -> dict[str, Any]:
    """Combine the two website sources, resolving explicit site-field links."""

    _require_object(site_data, "site", "content/site.json")
    _require_object(site_data, "identity", "content/site.json")
    portfolio = details_data.get("portfolio")
    if not isinstance(portfolio, dict):
        raise ContentModelError("content/details.json must contain a portfolio object")

    data = deepcopy(site_data)
    data["portfolio"] = _resolve_references(deepcopy(portfolio), site_data)
    return data


def _resolve_references(value: Any, site_data: dict[str, Any]) -> Any:
    if isinstance(value, list):
        return [_resolve_references(item, site_data) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value).issuperset({"$source"}):
        source = value["$source"]
        if not isinstance(source, str):
            raise ContentModelError("A $source reference must be a string path")
        resolved = get_path(site_data, source)
        template = value.get("$template", "{value}")
        if not isinstance(template, str):
            raise ContentModelError(f"The template for {source!r} must be a string")
        return template.replace("{value}", str(resolved))
    return {key: _resolve_references(item, site_data) for key, item in value.items()}


def get_path(data: dict[str, Any], path: str) -> Any:
    """Read a dotted object path. Array positions are intentionally unsupported."""

    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ContentModelError(f"Missing content field: {path}")
        current = current[part]
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted object path, rejecting accidental implicit schema changes."""

    parts = path.split(".")
    current: Any = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise ContentModelError(f"Missing content field: {path}")
        current = current[part]
    if not isinstance(current, dict) or parts[-1] not in current:
        raise ContentModelError(f"Missing content field: {path}")
    current[parts[-1]] = value


def iter_resume_items(resume_data: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for page_index, page in enumerate(resume_data.get("pages", [])):
        if not isinstance(page, dict):
            continue
        for block_index, block in enumerate(page.get("blocks", [])):
            if not isinstance(block, dict):
                continue
            for item_index, item in enumerate(block.get("items", [])):
                if isinstance(item, dict):
                    yield f"pages[{page_index}].blocks[{block_index}].items[{item_index}]", item


def validate_content_model(site_data: dict[str, Any], details_data: dict[str, Any], resume_data: dict[str, Any]) -> list[str]:
    """Return actionable errors without altering authored content."""

    errors: list[str] = []
    for key in ("site", "identity", "navigation"):
        if not isinstance(site_data.get(key), (dict, list)):
            errors.append(f"content/site.json is missing {key!r}")
    if "resume" in site_data:
        errors.append("content/site.json still contains legacy resume content; move it to content/resume.json")
    portfolio = details_data.get("portfolio")
    if not isinstance(portfolio, dict):
        errors.append("content/details.json must contain a portfolio object")
    if not isinstance(resume_data.get("pages"), list):
        errors.append("content/resume.json must contain a pages list")

    resume_ids: set[str] = set()
    for item_path, item in iter_resume_items(resume_data):
        item_id = item.get("id")
        if item_id is None:
            continue
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"resume item at {item_path} has an invalid id")
        elif item_id in resume_ids:
            errors.append(f"content/resume.json contains duplicate id: {item_id}")
        else:
            resume_ids.add(item_id)

    if isinstance(portfolio, dict):
        _validate_portfolio_relationships(portfolio, resume_ids, errors)
    _validate_shared_fields(site_data, resume_data, errors)
    return errors


def _validate_portfolio_relationships(portfolio: dict[str, Any], resume_ids: set[str], errors: list[str]) -> None:
    experience = portfolio.get("experience", {})
    items = experience.get("items", []) if isinstance(experience, dict) else []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"portfolio.experience.items[{index}] must be an object")
            continue
        item_id = item.get("id")
        resume_id = item.get("resume_id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"portfolio.experience.items[{index}] is missing stable id")
        if not isinstance(resume_id, str) or resume_id not in resume_ids:
            errors.append(f"portfolio.experience.items[{index}] has unknown resume_id: {resume_id!r}")

    case_studies = portfolio.get("case_studies", [])
    seen_case_ids: set[str] = set()
    for index, study in enumerate(case_studies):
        if not isinstance(study, dict):
            errors.append(f"portfolio.case_studies[{index}] must be an object")
            continue
        study_id = study.get("id")
        if not isinstance(study_id, str) or not study_id:
            errors.append(f"portfolio.case_studies[{index}] is missing stable id")
        elif study_id in seen_case_ids:
            errors.append(f"portfolio.case_studies contains duplicate id: {study_id}")
        else:
            seen_case_ids.add(study_id)
        linked_ids = study.get("resume_ids", [])
        if not isinstance(linked_ids, list) or not linked_ids:
            errors.append(f"portfolio.case_studies[{index}] needs one or more resume_ids")
        else:
            for resume_id in linked_ids:
                if not isinstance(resume_id, str) or resume_id not in resume_ids:
                    errors.append(f"portfolio.case_studies[{index}] has unknown resume_id: {resume_id!r}")


def _validate_shared_fields(site_data: dict[str, Any], resume_data: dict[str, Any], errors: list[str]) -> None:
    meta = resume_data.get("_meta", {})
    fields = meta.get("shared_fields", []) if isinstance(meta, dict) else []
    if not isinstance(fields, list):
        errors.append("resume._meta.shared_fields must be a list")
        return
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            errors.append(f"resume shared_fields[{index}] must be an object")
            continue
        source = field.get("source")
        target = field.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            errors.append(f"resume shared_fields[{index}] needs source and target paths")
            continue
        try:
            get_path(site_data, source)
            get_path(resume_data, target)
        except ContentModelError as error:
            errors.append(str(error))


def _require_object(data: dict[str, Any], key: str, label: str) -> None:
    if not isinstance(data.get(key), dict):
        raise ContentModelError(f"{label} is missing its {key!r} object")


SAFE_IMAGE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
