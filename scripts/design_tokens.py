"""Read the small DTCG-style design token file used by the CSS renderer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REQUIRED_COLORS = (
    "paper", "paper_deep", "ink", "ink_soft", "muted", "line", "line_dark", "green", "green_light", "orange", "orange_dark", "white",
)
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def load_design_tokens(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    colors = data.get("color", {})
    if not isinstance(colors, dict):
        raise ValueError("content/design-tokens.json must contain a color object")
    values: dict[str, str] = {}
    for name in REQUIRED_COLORS:
        token = colors.get(name)
        value = token.get("$value") if isinstance(token, dict) else None
        if not isinstance(value, str) or not HEX_COLOR.fullmatch(value):
            raise ValueError(f"Design token color.{name} must be a hex colour")
        values[name] = value
    return values


def render_css_variables(colors: dict[str, str]) -> str:
    return "\n".join(f"    --{name.replace('_', '-')}: {value};" for name, value in colors.items())
