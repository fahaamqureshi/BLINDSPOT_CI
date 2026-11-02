"""Reproduce the local release smoke test without loading dotenv or calling a model."""
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "final-audit"
BASE = "http://127.0.0.1:8016"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "DOTENV_DISABLED": "1", "BLINDSPOT_PROVIDER": "mock",
           "BLINDSPOT_PLANNER": "heuristic", "LIVE_API_ENABLED": "false",
           "BLINDSPOT_DATASET": "synthetic", "BLINDSPOT_PORT": "8016",
           "BLINDSPOT_RUNS_DIR": str(OUT / "runs"),
           "BLINDSPOT_CACHE_DIR": str(OUT / "cache"),
           "BLINDSPOT_PROVENANCE_PATH": str(OUT / "provenance.jsonl")}
    env.pop("MODEL_API_KEY", None)
    timings: dict[str, object] = {}
    client = httpx.Client(base_url=BASE, timeout=20)

    def start():
        began = time.perf_counter()
        proc = subprocess.Popen([sys.executable, "-m", "blindspot_ci.cli", "serve"],
                                cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        while time.perf_counter() - began < 15:
            try:
                if client.get("/health").status_code == 200:
                    return proc, round((time.perf_counter() - began) * 1000, 2)
            except httpx.TransportError:
                pass
            if proc.poll() is not None:
                raise RuntimeError("audit server failed to start")
            time.sleep(0.05)
        proc.terminate()
        proc.wait()
        raise RuntimeError("audit server startup timed out")

    def measured(name, method, path, **kwargs):
        began = time.perf_counter()
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        timings[name] = round((time.perf_counter() - began) * 1000, 2)
        return response

    proc, timings["startup_ms"] = start()
    try:
        for path in ("/", "/app", "/guide"):
            assert client.get(path).status_code == 200
        first = measured("evaluation_ms", "POST", "/api/experiment",
                         json={"max_steps": 8, "dataset": "synthetic"}).json()
        second = measured("cached_evaluation_ms", "POST", "/api/experiment",
                          json={"max_steps": 8, "dataset": "synthetic"}).json()
        assert first["summary"] == second["summary"]
        assert first["estimated_cost_usd"] == second["estimated_cost_usd"] == 0
        assert second["mode"] == "CACHE_MOCK_FIXTURE"
        run_id = first["id"]
        gate = measured("gate_ms", "GET", f"/api/runs/{run_id}/release-gate").json()
        assert gate["decision"] == "DEMO_ONLY"
        card = measured("report_ms", "GET", f"/api/runs/{run_id}/card")
        assert run_id in card.text and "attachment" in card.headers["content-disposition"]
        (OUT / "downloaded-card.md").write_text(card.text, encoding="utf-8")
        assert client.post("/api/experiment", json={"max_steps": 0}).status_code == 422
        assert client.get("/health", headers={"host": "evil.invalid"}).status_code == 403
        assert client.post("/api/experiment", json={},
                           headers={"origin": "https://evil.invalid"}).status_code == 403
        began = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(lambda _: client.get(f"/api/runs/{run_id}").status_code,
                                  range(20)))
        assert codes == [200] * 20
        timings["twenty_reads_four_workers_ms"] = round((time.perf_counter() - began) * 1000, 2)
        for _ in range(5):
            assert client.get(f"/api/runs/{run_id}/card").text == card.text
        proc.terminate()
        proc.wait(timeout=10)
        proc, timings["restart_ms"] = start()
        reopened = client.get(f"/api/runs/{run_id}").json()
        assert {key: reopened[key] for key in first} == first
        assert client.get(f"/api/runs/{run_id}/card").text == card.text
        evidence = {"python": sys.version.split()[0], "platform": sys.platform,
                    "run_id": run_id, "summary": first["summary"], "gate": gate["decision"],
                    "cache_hits": len(second["steps"]), "timings_ms": timings,
                    "paid_calls": 0, "persistence": "PASS", "concurrent_reads": codes}
        (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        client.close()


if __name__ == "__main__":
    main()
