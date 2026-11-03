import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from blindspot_ci.integrations import install_skill


@pytest.mark.parametrize(("target", "folder"), [("codex", ".agents"), ("claude", ".claude")])
def test_project_skill_install_is_idempotent_and_preserves_edits(tmp_path, target, folder):
    destination = install_skill(tmp_path, target)
    assert destination == tmp_path / folder / "skills/blindspot-ci/SKILL.md"
    assert install_skill(tmp_path, target) == destination
    destination.write_text("owner changes", encoding="utf-8")
    with pytest.raises(FileExistsError):
        install_skill(tmp_path, target)
    assert destination.read_text() == "owner changes"


def test_agent_json_workflow_reads_same_saved_run(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]), "DOTENV_DISABLED": "1"}
    for name in ("BLINDSPOT_WORKSPACE", "BLINDSPOT_RUNS_DIR", "BLINDSPOT_CACHE_DIR", "BLINDSPOT_PROVENANCE_PATH", "MODEL_API_KEY"):
        env.pop(name, None)
    workspace = tmp_path / "evaluation"

    def run(*args):
        result = subprocess.run([sys.executable, "-m", "blindspot_ci.cli", *args],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stderr or result.stdout
        return result.stdout

    run("init", str(workspace))
    report = json.loads(run("--workspace", str(workspace), "experiment", "--mock", "--steps", "5", "--json"))
    saved = json.loads(run("--workspace", str(workspace), "report", "--run", report["id"], "--json"))
    assert saved["id"] == report["id"]
    assert saved["summary"] == report["summary"]
    assert saved["summary"]["tested"] == 5 and saved["estimated_cost_usd"] == 0
    assert saved["mode"] == "MOCK_FIXTURE" and len(saved["configured_case_ids"]) == 5
