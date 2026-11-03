import os

import pytest

os.environ["DOTENV_DISABLED"] = "1"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Keep every test away from the real cache and provenance log."""
    monkeypatch.setenv("BLINDSPOT_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("BLINDSPOT_PROVIDER", "mock")
    monkeypatch.setenv("BLINDSPOT_PLANNER", "heuristic")
    monkeypatch.setenv("LIVE_API_ENABLED", "false")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("BLINDSPOT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("BLINDSPOT_PROVENANCE_PATH", str(tmp_path / "provenance.jsonl"))
