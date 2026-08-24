"""Content loading, safe field references, and relationship validation.

``site.json`` owns the site-wide settings, navigation, and ordered website
section manifest. The section records stay in small files below
``content/details/website/``. The resume remains independent and can share
selected factual fields through its explicit ``_meta.shared_fields`` list.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterator

from project_paths import ASSET_RECORD_PATH, CONTENT_DIR, FACTS_CONTENT_PATH, RESUME_CONTENT_PATH, RESUME_DIR, SITE_CONTENT_PATH


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


def load_resume_content() -> dict[str, Any]:
    """Compose section files into the legacy resume shape used by mappers."""

    manifest = read_json(RESUME_CONTENT_PATH)
    sections = manifest.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ContentModelError("content/details/resume.json must contain sections")
    composed: dict[str, Any] = {"pages": [{"title": "Resume", "blocks": []}]}
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("id"), str) or not isinstance(section.get("file"), str):
            raise ContentModelError("Every resume section needs an id and JSON file")
        value = read_json(RESUME_DIR / section["file"])
        if section["id"] == "intro":
            composed.update({key: value[key] for key in ("name", "headline", "contact", "general_skills") if key in value})
        else:
            blocks = value.get("blocks")
            if not isinstance(blocks, list):
                raise ContentModelError(f"Resume section {section['id']!r} must contain a blocks list")
            composed["pages"][0]["blocks"].extend(deepcopy(blocks))
    meta = manifest.get("_meta")
    if isinstance(meta, dict):
        composed["_meta"] = deepcopy(meta)
    return composed


def write_resume_content(resume_data: dict[str, Any]) -> None:
    """Write the composed resume shape back to its manifest section files."""

    manifest = read_json(RESUME_CONTENT_PATH)
    blocks = resume_data.get("pages", [{}])[0].get("blocks", [])
    by_heading = {str(block.get("heading")): block for block in blocks if isinstance(block, dict)}
    for section in manifest["sections"]:
        section_id = section["id"]
        path = RESUME_DIR / section["file"]
        current = read_json(path)
        if section_id == "intro":
            current.update({key: resume_data.get(key, current.get(key)) for key in ("name", "headline", "contact", "general_skills")})
        else:
            headings = [str(block.get("heading")) for block in current.get("blocks", []) if isinstance(block, dict)]
            current["blocks"] = [by_heading[heading] for heading in headings if heading in by_heading]
        write_json_atomic(path, current)


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
    metadata: dict[str, Any] | None = None


def load_details_content() -> dict[str, Any]:
    """Load the website manifest from site.json and compose its section files."""

    manifest = read_json(SITE_CONTENT_PATH)
    sections = _detail_section_records(manifest)
    website: dict[str, Any] = {}
    for section in sections:
        if section.id in website:
            raise ContentModelError(f"content/site.json contains duplicate section id: {section.id}")
        if section.path:
            value = read_json_value(section.path)
            if not isinstance(value, (dict, list)):
                raise ContentModelError(f"{section.path.name} must contain a JSON object or array")
            website[section.id] = value
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
            if not _is_included(value, item.path):
                continue
            values.append(value)
        if section.metadata:
            website[section.id] = {**deepcopy(section.metadata), "items": values}
        else:
            website[section.id] = values
    return {"website": website}


def detail_source_paths() -> list[Path]:
    """Return the manifest and every file it currently owns, in stable order."""

    manifest = read_json(SITE_CONTENT_PATH)
    paths = [SITE_CONTENT_PATH]
    for section in _detail_section_records(manifest):
        if section.path:
            paths.append(section.path)
        paths.extend(item.path for item in section.items)
    return paths


def write_details_content(details_data: dict[str, Any]) -> None:
    """Persist a composed details object back to its existing section files."""

    website = details_data.get("website")
    if not isinstance(website, dict):
        raise ContentModelError("website content must be an object")
    manifest = read_json(SITE_CONTENT_PATH)
    sections = _detail_section_records(manifest)
    expected_ids = {section.id for section in sections}
    supplied_ids = set(website)
    if supplied_ids != expected_ids:
        missing = sorted(expected_ids - supplied_ids)
        extra = sorted(supplied_ids - expected_ids)
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if extra:
            parts.append("unexpected " + ", ".join(extra))
        raise ContentModelError("Website section manifest mismatch: " + "; ".join(parts))
    manifest_changed = False
    for section in sections:
        value = website[section.id]
        if section.path:
            if not isinstance(value, (dict, list)):
                raise ContentModelError(f"details section {section.id!r} must be an object or list")
            write_json_atomic(section.path, value)
            continue
        manifest_changed = _write_collection_section(manifest, section, value) or manifest_changed
    if manifest_changed:
        write_json_atomic(SITE_CONTENT_PATH, manifest)


def _write_collection_section(manifest: dict[str, Any], section: DetailSection, value: Any) -> bool:
    if section.metadata:
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            raise ContentModelError(f"website collection {section.id!r} must contain an items list")
        value = value["items"]
    elif not isinstance(value, list):
        raise ContentModelError(f"website collection {section.id!r} must be a list")
    known_paths = {item.id: item.relative_path for item in section.items}
    records: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ContentModelError(f"website collection {section.id}[{index}] must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not _SAFE_DETAIL_ID.fullmatch(item_id):
            raise ContentModelError(f"website collection {section.id}[{index}] needs a safe stable id")
        if item_id in seen_ids:
            raise ContentModelError(f"website collection {section.id} contains duplicate id: {item_id}")
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
    sections = manifest.get("website", {}).get("sections")
    if not isinstance(sections, list):  # Already checked by _detail_section_records.
        raise ContentModelError("content/site.json must contain website.sections")
    for section in sections:
        if isinstance(section, dict) and section.get("id") == section_id:
            return section
    raise ContentModelError(f"content/site.json is missing section {section_id!r}")


def _detail_section_records(manifest: dict[str, Any]) -> list[DetailSection]:
    website = manifest.get("website")
    sections = website.get("sections") if isinstance(website, dict) else None
    if not isinstance(sections, list) or not sections:
        raise ContentModelError("content/site.json must contain website.sections")
    records: list[DetailSection] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ContentModelError(f"website manifest section {index} must be an object")
        section_id = section.get("id")
        relative_path = section.get("file")
        item_records = section.get("items")
        if not isinstance(section_id, str) or not section_id:
            raise ContentModelError(f"website manifest section {index} needs an id")
        if isinstance(relative_path, str) and relative_path.endswith(".json") and "items" not in section:
            records.append(DetailSection(section_id, path=_details_path(relative_path)))
            continue
        if "file" in section:
            raise ContentModelError(f"website manifest section {section_id!r} cannot use both file and items")
        if not isinstance(item_records, list) or not item_records:
            raise ContentModelError(f"website manifest collection {section_id!r} needs one or more items")
        items: list[DetailItem] = []
        seen_ids: set[str] = set()
        for item_index, item in enumerate(item_records):
            if not isinstance(item, dict):
                raise ContentModelError(f"website manifest collection {section_id!r} item {item_index} must be an object")
            item_id = item.get("id")
            item_path = item.get("file")
            if not isinstance(item_id, str) or not _SAFE_DETAIL_ID.fullmatch(item_id):
                raise ContentModelError(f"website manifest collection {section_id!r} item {item_index} needs a safe id")
            if item_id in seen_ids:
                raise ContentModelError(f"website manifest collection {section_id!r} contains duplicate id: {item_id}")
            if not isinstance(item_path, str) or not item_path.endswith(".json"):
                raise ContentModelError(f"website manifest collection {section_id!r} item {item_id!r} needs a JSON file path")
            seen_ids.add(item_id)
            items.append(DetailItem(item_id, item_path, _details_path(item_path)))
        metadata = {key: value for key, value in section.items() if key not in {"id", "items"}}
        records.append(DetailSection(section_id, items=tuple(items), metadata=metadata or None))
    return records


_SAFE_DETAIL_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def _default_item_path(section_id: str, item_id: str) -> str:
    if section_id == "case_studies":
        return f"details/website/projects/{item_id}.json"
    return f"details/website/{section_id.replace('_', '-')}/{item_id}.json"


def _details_path(relative_path: str) -> Path:
    path = (CONTENT_DIR / relative_path).resolve()
    try:
        path.relative_to(CONTENT_DIR.resolve())
    except ValueError as error:
        raise ContentModelError(f"Details file is outside content/: {relative_path}") from error
    return path


def _is_included(record: dict[str, Any], path: Path) -> bool:
    """Return an optional content record's inclusion state, rejecting ambiguity."""

    include = record.get("include", True)
    if not isinstance(include, bool):
        raise ContentModelError(f"{path.relative_to(CONTENT_DIR)} include must be true or false")
    return include


def compose_site_content(
    site_data: dict[str, Any],
    details_data: dict[str, Any],
    facts_data: dict[str, Any] | None = None,
    asset_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine website sources, resolving canonical fact and asset references."""

    _require_object(site_data, "site", "content/site.json")
    _require_object(site_data, "identity", "content/site.json")
    website = details_data.get("website")
    if not isinstance(website, dict):
        raise ContentModelError("content/site.json must contain a website object")

    facts = facts_data if facts_data is not None else read_json(FACTS_CONTENT_PATH)
    _validate_facts(facts)
    assets = asset_data if asset_data is not None else read_json(ASSET_RECORD_PATH)
    _validate_assets(assets)
    data = _resolve_references(deepcopy(site_data), site_data, facts, assets)
    data["website"] = _resolve_references(deepcopy(website), data, facts, assets)
    return data


def _resolve_references(value: Any, site_data: dict[str, Any], facts_data: dict[str, Any], asset_data: dict[str, Any]) -> Any:
    if isinstance(value, list):
        return [_resolve_references(item, site_data, facts_data, asset_data) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value).issuperset({"$source"}):
        source = value["$source"]
        if not isinstance(source, str):
            raise ContentModelError("A $source reference must be a string path")
        source_data = facts_data if source.startswith("facts.") else asset_data if source.startswith("assets.") else site_data
        source_path = source.removeprefix("facts.").removeprefix("assets.")
        resolved = get_path(source_data, source_path)
        template = value.get("$template")
        if template is None:
            return deepcopy(resolved)
        if not isinstance(template, str):
            raise ContentModelError(f"The template for {source!r} must be a string")
        return template.replace("{value}", str(resolved))
    return {key: _resolve_references(item, site_data, facts_data, asset_data) for key, item in value.items()}


def _validate_facts(facts_data: dict[str, Any]) -> None:
    if not isinstance(facts_data, dict) or facts_data.get("schema_version") != 1:
        raise ContentModelError("content/facts.json must use schema_version 1")
    identity = facts_data.get("identity")
    if not isinstance(identity, dict):
        raise ContentModelError("content/facts.json must contain an identity object")
    for key in ("name", "location", "phone", "email", "website"):
        if not isinstance(identity.get(key), str) or not identity[key].strip():
            raise ContentModelError(f"content/facts.json identity is missing {key!r}")


def _validate_assets(asset_data: dict[str, Any]) -> None:
    if not isinstance(asset_data, dict) or asset_data.get("schema_version") != 1:
        raise ContentModelError("content/assets/asset-record.json must use schema_version 1")
    images = asset_data.get("images")
    if not isinstance(images, dict) or not images:
        raise ContentModelError("content/assets/asset-record.json must contain an images object")
    for image_id, image in images.items():
        if not isinstance(image_id, str) or not _SAFE_DETAIL_ID.fullmatch(image_id) or not isinstance(image, dict):
            raise ContentModelError("content/assets/asset-record.json images must use safe IDs and object records")
        for key in ("src", "alt", "title"):
            if not isinstance(image.get(key), str) or not image[key].strip():
                raise ContentModelError(f"content/assets/asset-record.json image {image_id!r} is missing {key!r}")
        display = image.get("display")
        if not isinstance(display, dict) or not all(isinstance(value, bool) for value in display.values()):
            raise ContentModelError(f"content/assets/asset-record.json image {image_id!r} needs boolean display flags")

def resolve_fact_references(value: Any, facts_data: dict[str, Any]) -> Any:
    """Resolve ``facts.*`` references while preserving the surrounding shape."""

    if isinstance(value, list):
        return [resolve_fact_references(item, facts_data) for item in value]
    if not isinstance(value, dict):
        return value
    if "$source" in value:
        source = value["$source"]
        if not isinstance(source, str) or not source.startswith("facts."):
            raise ContentModelError("A fact reference must use a facts.* path")
        resolved = get_path(facts_data, source.removeprefix("facts."))
        template = value.get("$template")
        if "$template" not in value:
            return deepcopy(resolved)
        if not isinstance(template, str):
            raise ContentModelError(f"The template for {source!r} must be a string")
        return template.replace("{value}", str(resolved))
    return {key: resolve_fact_references(item, facts_data) for key, item in value.items()}


def restore_fact_references(original: Any, updated: Any, facts_data: dict[str, Any]) -> Any:
    """Keep unchanged authored fact references after a projection is edited."""

    if isinstance(original, dict) and "$source" in original:
        resolved = resolve_fact_references(original, facts_data)
        return original if updated == resolved else updated
    if isinstance(original, list) and isinstance(updated, list):
        return [restore_fact_references(source, value, facts_data) for source, value in zip(original, updated)]
    if isinstance(original, dict) and isinstance(updated, dict):
        return {
            key: restore_fact_references(value, updated.get(key), facts_data)
            if key in updated
            else value
            for key, value in original.items()
        }
    return updated


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


def validate_content_model(
    site_data: dict[str, Any], details_data: dict[str, Any], resume_data: dict[str, Any], facts_data: dict[str, Any] | None = None
) -> list[str]:
    """Return actionable errors without altering authored content."""

    errors: list[str] = []
    for key in ("site", "identity", "navigation"):
        if not isinstance(site_data.get(key), (dict, list)):
            errors.append(f"content/site.json is missing {key!r}")
    site_settings = site_data.get("site")
    if isinstance(site_settings, dict):
        for key in ("url", "social_image_alt"):
            if not isinstance(site_settings.get(key), str) or not site_settings[key].strip():
                errors.append(f"content/site.json site is missing {key!r}")
        social_image = site_settings.get("social_image")
        if not isinstance(social_image, (str, dict)):
            errors.append("content/site.json site is missing 'social_image'")
        if isinstance(site_settings.get("url"), str) and not site_settings["url"].startswith("https://"):
            errors.append("content/site.json site.url must be an https URL")
    if "resume" in site_data:
        errors.append("content/site.json still contains legacy resume content; move it to content/details/resume.json")
    website = details_data.get("website")
    if not isinstance(website, dict):
        errors.append("content/site.json must contain a website object")
    if not isinstance(resume_data.get("pages"), list):
        errors.append("content/details/resume.json must contain sections")

    resume_ids: set[str] = set()
    for item_path, item in iter_resume_items(resume_data):
        item_id = item.get("id")
        if item_id is None:
            continue
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"resume item at {item_path} has an invalid id")
        elif item_id in resume_ids:
            errors.append(f"content/details/resume.json contains duplicate id: {item_id}")
        else:
            resume_ids.add(item_id)

    if isinstance(website, dict):
        _validate_portfolio_relationships(website, resume_ids, errors)
    _validate_shared_fields(site_data, resume_data, facts_data, errors)
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
        if study.get("placeholders"):
            errors.append(f"portfolio.case_studies[{index}] contains public placeholders; keep planned assets in CONTENT_TODO.md")


def _validate_shared_fields(
    site_data: dict[str, Any], resume_data: dict[str, Any], facts_data: dict[str, Any] | None, errors: list[str]
) -> None:
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
            source_data = facts_data if source.startswith("facts.") else site_data
            source_path = source.removeprefix("facts.") if source.startswith("facts.") else source
            if source_data is None:
                raise ContentModelError("content/details/facts.json is required for facts shared fields")
            get_path(source_data, source_path)
            get_path(resume_data, target)
        except ContentModelError as error:
            errors.append(str(error))


def _require_object(data: dict[str, Any], key: str, label: str) -> None:
    if not isinstance(data.get(key), dict):
        raise ContentModelError(f"{label} is missing its {key!r} object")


SAFE_IMAGE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
