from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from portfolio_workflow import generated_drift, load_content, validate_site  # noqa: E402
from design_tokens import load_design_tokens  # noqa: E402
from project_paths import DESIGN_TOKENS_PATH  # noqa: E402
from site_renderer import render_documentation_card, render_engineering_styles  # noqa: E402


class SiteMaintenanceTests(unittest.TestCase):
    def test_content_assets_and_links_validate(self) -> None:
        self.assertEqual(validate_site(), [])

    def test_generated_artifacts_match_renderer(self) -> None:
        self.assertEqual(generated_drift(), [])

    def test_rendered_page_has_absolute_recruiter_sharing_metadata(self) -> None:
        html = load_content()
        from site_renderer import render_engineering_index

        rendered = render_engineering_index(html)
        self.assertIn('<link rel="canonical" href="https://ashwin-conrad.github.io/">', rendered)
        self.assertIn('<meta property="og:url" content="https://ashwin-conrad.github.io/">', rendered)
        self.assertIn('meta property="og:image" content="https://ashwin-conrad.github.io/assets/', rendered)
        self.assertIn('meta name="twitter:card" content="summary_large_image">', rendered)

    def test_asset_display_flags_hide_optional_documentation_metadata(self) -> None:
        image = deepcopy(load_content()["website"]["documentation"]["items"][0])
        image["display"] = {"figure": False, "title": False, "caption": False}
        markup = render_documentation_card(image)
        self.assertNotIn("Figure 06", markup)
        self.assertNotIn("Competition context", markup)
        self.assertNotIn("Vehicle systems are built", markup)

    def test_text_style_tokens_are_emitted_for_global_site_configuration(self) -> None:
        tokens = load_design_tokens(DESIGN_TOKENS_PATH)
        title = tokens.text_styles["site.title"]
        self.assertEqual(title.font_weight, "600")
        self.assertEqual(title.color, tokens.colors["ink"])
        styles = render_engineering_styles(tokens)
        self.assertIn("--text-site-title-font-size: clamp(2.5rem, 4.6vw, 5.1rem);", styles)
        self.assertIn("font-size: var(--text-site-title-font-size);", styles)


if __name__ == "__main__":
    unittest.main()
