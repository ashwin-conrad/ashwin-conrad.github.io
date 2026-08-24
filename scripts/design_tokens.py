"""Load design tokens shared by the website and generated resume.

The token file uses a small, DTCG-inspired shape. Colours remain available as
a mapping for the existing theme renderer, while named typography styles carry
the complete text treatment (family, size, weight, style, leading, tracking,
colour, and transform) for both outputs.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_COLORS = (
    "paper", "paper_deep", "ink", "ink_soft", "muted", "line", "line_dark", "green", "green_light",
    "accent", "accent_dark", "accent_hover", "white", "on_dark", "on_dark_muted", "dark_line",
)
REQUIRED_TEXT_STYLE_FIELDS = (
    "fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing", "color", "textTransform",
)
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")
COLOR_REFERENCE = re.compile(r"^\{color\.([a-z0-9_.-]+)\}$")
FONT_REFERENCE = re.compile(r"^\{font\.family\.([a-z0-9_.-]+)\}$")


@dataclass(frozen=True)
class TextStyle:
    """A complete, platform-neutral text treatment from the token source."""

    font_family: str
    font_size: str
    font_weight: str
    font_style: str
    line_height: str
    letter_spacing: str
    color: str
    text_transform: str


@dataclass(frozen=True)
class DesignTokens(Mapping[str, str]):
    """Resolved token values with backwards-compatible colour mapping access."""

    colors: dict[str, str]
    text_styles: dict[str, TextStyle]

    def __getitem__(self, key: str) -> str:
        return self.colors[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.colors)

    def __len__(self) -> int:
        return len(self.colors)


def load_design_tokens(path: Path) -> DesignTokens:
    """Read and resolve the project's colour, font, and text-style tokens."""

    data = json.loads(path.read_text(encoding="utf-8"))
    colors = _resolve_colors(data)
    font_families = _resolve_font_families(data)
    text_styles = _resolve_text_styles(data, colors, font_families)
    return DesignTokens(colors=colors, text_styles=text_styles)


def _resolve_colors(data: dict[str, Any]) -> dict[str, str]:
    colors = data.get("color", {})
    if not isinstance(colors, dict):
        raise ValueError("content/styles.json must contain a color object")

    raw_values: dict[str, str] = {}

    def collect(group: dict[str, Any], prefix: str = "") -> None:
        for name, token in group.items():
            if name.startswith("$"):
                continue
            token_name = f"{prefix}.{name}" if prefix else name
            if not isinstance(token, dict):
                raise ValueError(f"Design token color.{token_name} must be an object")
            if "$value" in token:
                value = token["$value"]
                if not isinstance(value, str):
                    raise ValueError(f"Design token color.{token_name} must be a hex colour or colour alias")
                raw_values[token_name] = value
            else:
                collect(token, token_name)

    collect(colors)
    missing = [name for name in REQUIRED_COLORS if name not in raw_values]
    if missing:
        raise ValueError(f"Design token color.{missing[0]} is required")

    values: dict[str, str] = {}

    def resolve(name: str, trail: tuple[str, ...] = ()) -> str:
        if name in values:
            return values[name]
        if name in trail:
            raise ValueError(f"Design token color.{name} has a circular colour alias")

        value = raw_values[name]
        if HEX_COLOR.fullmatch(value):
            values[name] = value
            return value
        reference = COLOR_REFERENCE.fullmatch(value)
        if reference and reference.group(1) in raw_values:
            resolved = resolve(reference.group(1), (*trail, name))
            values[name] = resolved
            return resolved
        raise ValueError(f"Design token color.{name} must be a hex colour or valid colour alias")

    for name in raw_values:
        resolve(name)
    return values


def _resolve_font_families(data: dict[str, Any]) -> dict[str, str]:
    family_group = data.get("font", {}).get("family", {}) if isinstance(data.get("font"), dict) else {}
    if not isinstance(family_group, dict):
        raise ValueError("Design tokens font.family must be an object")

    values: dict[str, str] = {}
    for name, token in family_group.items():
        if not isinstance(token, dict) or "$value" not in token:
            raise ValueError(f"Design token font.family.{name} must contain a $value")
        value = token["$value"]
        if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
            values[name] = ", ".join(_css_font_name(item) for item in value)
        elif isinstance(value, str) and value.strip():
            values[name] = value.strip()
        else:
            raise ValueError(f"Design token font.family.{name} must be a non-empty font family list or string")
    if not values:
        raise ValueError("Design tokens must define at least one font.family token")
    return values


def _css_font_name(value: str) -> str:
    # Generic family names must remain bare in CSS; named families are quoted.
    return value if value.lower() in {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"} else f'"{value}"'


def _resolve_text_styles(
    data: dict[str, Any], colors: Mapping[str, str], font_families: Mapping[str, str]
) -> dict[str, TextStyle]:
    text = data.get("text", {})
    if not isinstance(text, dict):
        raise ValueError("Design tokens must contain a text object")
    raw_styles: dict[str, dict[str, Any]] = {}

    def collect(group: dict[str, Any], prefix: str = "") -> None:
        for name, token in group.items():
            if name.startswith("$"):
                continue
            token_name = f"{prefix}.{name}" if prefix else name
            if not isinstance(token, dict):
                raise ValueError(f"Design token text.{token_name} must be an object")
            if "$value" in token:
                if token.get("$type") != "typography" or not isinstance(token["$value"], dict):
                    raise ValueError(f"Design token text.{token_name} must be a typography token")
                raw_styles[token_name] = token["$value"]
            else:
                collect(token, token_name)

    collect(text)
    if not raw_styles:
        raise ValueError("Design tokens must define at least one text style")

    styles: dict[str, TextStyle] = {}
    for name, value in raw_styles.items():
        missing = [field for field in REQUIRED_TEXT_STYLE_FIELDS if field not in value]
        if missing:
            raise ValueError(f"Design token text.{name} is missing {missing[0]}")
        unknown = sorted(set(value) - set(REQUIRED_TEXT_STYLE_FIELDS))
        if unknown:
            raise ValueError(f"Design token text.{name} has an unsupported field: {unknown[0]}")
        fields = {field: _resolve_text_field(name, field, value[field], colors, font_families) for field in REQUIRED_TEXT_STYLE_FIELDS}
        styles[name] = TextStyle(
            font_family=fields["fontFamily"],
            font_size=fields["fontSize"],
            font_weight=fields["fontWeight"],
            font_style=fields["fontStyle"],
            line_height=fields["lineHeight"],
            letter_spacing=fields["letterSpacing"],
            color=fields["color"],
            text_transform=fields["textTransform"],
        )
    for required_style in ("site.body", "site.title", "resume.name", "resume.body", "resume.section_heading"):
        if required_style not in styles:
            raise ValueError(f"Design token text.{required_style} is required")
    return styles


def _resolve_text_field(
    style_name: str, field_name: str, value: Any, colors: Mapping[str, str], font_families: Mapping[str, str]
) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)) or not str(value).strip():
        raise ValueError(f"Design token text.{style_name}.{field_name} must be a non-empty string or number")
    raw = str(value).strip()
    if field_name == "color":
        reference = COLOR_REFERENCE.fullmatch(raw)
        if reference and reference.group(1) in colors:
            return colors[reference.group(1)]
        if HEX_COLOR.fullmatch(raw):
            return raw
        raise ValueError(f"Design token text.{style_name}.color must be a valid colour token reference or hex colour")
    if field_name == "fontFamily":
        reference = FONT_REFERENCE.fullmatch(raw)
        if reference and reference.group(1) in font_families:
            return font_families[reference.group(1)]
        raise ValueError(f"Design token text.{style_name}.fontFamily must reference font.family")
    return raw


def render_css_variables(tokens: DesignTokens) -> str:
    """Render all resolved values as CSS custom properties."""

    color_lines = [f"    --{name.replace('.', '-').replace('_', '-')}: {value};" for name, value in tokens.colors.items()]
    style_lines: list[str] = []
    for name, style in tokens.text_styles.items():
        prefix = f"--text-{name.replace('.', '-').replace('_', '-')}"
        style_lines.extend(
            (
                f"    {prefix}-font-family: {style.font_family};",
                f"    {prefix}-font-size: {style.font_size};",
                f"    {prefix}-font-weight: {style.font_weight};",
                f"    {prefix}-font-style: {style.font_style};",
                f"    {prefix}-line-height: {style.line_height};",
                f"    {prefix}-letter-spacing: {style.letter_spacing};",
                f"    {prefix}-color: {style.color};",
                f"    {prefix}-text-transform: {style.text_transform};",
            )
        )
    return "\n".join((*color_lines, *style_lines))
