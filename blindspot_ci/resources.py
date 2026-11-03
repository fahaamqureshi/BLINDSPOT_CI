"""Locate the public demonstration assets in a checkout or an installed wheel."""
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
CHECKOUT = PACKAGE.parent
PUBLIC_ROOT = (CHECKOUT if (CHECKOUT / "fixtures" / "mock_responses.json").is_file()
               else PACKAGE / "_bundled")
RESOURCE_ROOT = (Path(os.environ["BLINDSPOT_WORKSPACE"]).expanduser().resolve()
                 if os.environ.get("BLINDSPOT_WORKSPACE") else PUBLIC_ROOT)
