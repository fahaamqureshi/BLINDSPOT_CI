"""Locate the public demonstration assets in a checkout or an installed wheel."""
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
CHECKOUT = PACKAGE.parent
RESOURCE_ROOT = (CHECKOUT if (CHECKOUT / "fixtures" / "mock_responses.json").is_file()
                 else PACKAGE / "_bundled")
