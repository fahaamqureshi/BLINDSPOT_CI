"""Exercise an installed wheel outside the checkout with public fixtures and no network calls."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SMOKE = r'''
import json, os
from pathlib import Path
import blindspot_ci
from fastapi.testclient import TestClient
from blindspot_ci.api import app
from blindspot_ci.experiment.cases import load_named_dataset
root = Path(os.environ["BLINDSPOT_WHEEL_ROOT"]).resolve()
assert Path(blindspot_ci.__file__).resolve().is_relative_to(root)
client = TestClient(app)
for route in ("/", "/app", "/guide", "/health", "/api/info", "/api/scenarios"):
    assert client.get(route).status_code == 200, route
assert len(client.get("/api/examples").json()) == 2
run = client.post("/api/experiment", json={"max_steps": 8}).json()
assert run["summary"]["tested"] == 5 and run["estimated_cost_usd"] == 0
run_id = run["id"]
assert client.get(f"/api/runs/{run_id}/release-gate").json()["decision"] == "DEMO_ONLY"
assert client.get(f"/api/runs/{run_id}/card").status_code == 200
for case in load_named_dataset("synthetic").cases:
    assert client.get(f"/api/cases/{case}/image?dataset=synthetic").status_code == 200
assert client.post(f"/api/runs/{run_id}/audit").status_code == 403
print(json.dumps({"installed_wheel": "PASS", "public_assets": "PASS",
                  "mock_checks": run["summary"]["tested"], "gate": "DEMO_ONLY", "paid_calls": 0}))
'''


def verify(wheel: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="blindspot-wheel-") as temporary:
        root = Path(temporary)
        target = root / "installed"
        target.mkdir()
        forbidden = {".env", "real", "open", "hard", "video", "coco", "generated", "corrupted"}
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.infolist():
                path = (target / member.filename).resolve()
                parts = Path(member.filename).parts
                if (not path.is_relative_to(target) or "\\" in member.filename
                        or forbidden.intersection(parts)
                        or any(part.endswith("_manifest.json") for part in parts)):
                    raise ValueError("wheel contains an unsafe or private asset path")
                if not member.is_dir():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(member))
        env = {**os.environ, "PYTHONPATH": str(target), "DOTENV_DISABLED": "1",
               "BLINDSPOT_WHEEL_ROOT": str(target), "BLINDSPOT_PROVIDER": "mock",
               "BLINDSPOT_PLANNER": "heuristic", "BLINDSPOT_DATASET": "synthetic",
               "LIVE_API_ENABLED": "false", "BLINDSPOT_ALLOWED_HOSTS": "testserver",
               "BLINDSPOT_RUNS_DIR": str(root / "runs"),
               "BLINDSPOT_CACHE_DIR": str(root / "cache"),
               "BLINDSPOT_PROVENANCE_PATH": str(root / "provenance.jsonl")}
        env.pop("MODEL_API_KEY", None)
        result = subprocess.run([sys.executable, "-c", SMOKE], cwd=root, env=env,
                                capture_output=True, text=True, check=False, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    print(verify(args.wheel.resolve()))


if __name__ == "__main__":
    main()
