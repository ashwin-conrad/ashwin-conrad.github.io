from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from portfolio_workflow import generated_drift, validate_site  # noqa: E402


class SiteMaintenanceTests(unittest.TestCase):
    def test_content_assets_and_links_validate(self) -> None:
        self.assertEqual(validate_site(), [])

    def test_generated_artifacts_match_renderer(self) -> None:
        self.assertEqual(generated_drift(), [])


if __name__ == "__main__":
    unittest.main()
