from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from blindspot_ci.media import is_allowed_image_url
from blindspot_ci.models import ProviderResult, Scenario
from blindspot_ci.providers.sam_output import parse_sam_output


class MetaApiError(RuntimeError):
    pass


def _output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "".join(chunks)


class _MetaBase:
    name = "meta"

    def __init__(self, api_key: str, base_url: str = "https://api.meta.ai/v1", timeout: float = 45.0, retries: int = 2):
        if not api_key:
            raise ValueError("MODEL_API_KEY is required for the live Meta adapter")
        self.api_key, self.base_url, self.timeout, self.retries = api_key, base_url.rstrip("/"), timeout, retries

    @staticmethod
    def _not_retryable(exc: Exception) -> bool:
        """A 4xx other than timeout, conflict or rate limit will fail again, so stop at once."""
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", 0)
        return isinstance(exc, httpx.HTTPStatusError) and 400 <= code < 500 and code not in {408, 409, 429}

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        try:
            return min(float(retry_after), 5.0) if retry_after else 0.5 * (2**attempt) + random.random() * 0.2
        except ValueError:  # Retry-After may be an HTTP date; fall back to backoff
            return 0.5 * (2**attempt) + random.random() * 0.2

    def _describe(self, exc: Exception) -> str:
        """Error text with the server's explanation, and the key redacted."""
        text = str(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            text += f" | server said: {response.text[:300]}"
        return text.replace(self.api_key, "[redacted]")

    def _post_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST with stream=true and collect output text and usage from server-sent events."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   "Accept": "text/event-stream"}
        body = {**payload, "stream": True}
        for attempt in range(self.retries + 1):
            try:
                with httpx.stream("POST", f"{self.base_url}/responses", headers=headers, json=body,
                                  timeout=self.timeout) as response:
                    if response.status_code in {408, 409, 429, 500, 502, 503, 504} and attempt < self.retries:
                        time.sleep(min(0.5 * (2**attempt) + random.random() * 0.2, 5.0))
                        continue
                    if response.status_code >= 400:
                        response.read()
                        response.raise_for_status()
                    return self._collect_events(response.iter_lines())
            except httpx.HTTPError as exc:
                if self._not_retryable(exc):
                    raise MetaApiError(f"Meta API request failed: {self._describe(exc)}") from exc
                if attempt >= self.retries:
                    raise MetaApiError(f"Meta API request failed after retries: {self._describe(exc)}") from exc
        raise MetaApiError("Meta API request failed")

    def _collect_events(self, lines) -> dict[str, Any]:
        lanes: dict[tuple, str] = {}
        deltas: dict[tuple, list[str]] = {}
        usage: dict[str, Any] = {}
        for line in lines:
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            kind = event.get("type", "")
            lane = (event.get("output_index", 0), event.get("content_index", 0))
            if kind == "response.output_text.delta":
                deltas.setdefault(lane, []).append(event.get("delta", ""))
            elif kind == "response.output_text.done":
                lanes[lane] = event.get("text", "")
            elif kind == "response.content_part.done" and event.get("part", {}).get("type") == "output_text":
                lanes[lane] = event["part"].get("text", "")
            elif kind == "response.completed":
                usage = event.get("response", {}).get("usage", {}) or {}
            elif kind in {"response.failed", "error"}:
                detail = json.dumps(event.get("response", {}).get("error") or event.get("error") or event)[:300]
                raise MetaApiError(f"Meta API stream failed: {detail.replace(self.api_key, '[redacted]')}")
        for lane, parts in deltas.items():
            lanes.setdefault(lane, "".join(parts))
        return {"output_text": "".join(lanes[k] for k in sorted(lanes)), "usage": usage}

    def _post(self, payload: dict[str, Any], path: str = "/responses") -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(self.retries + 1):
            try:
                response = httpx.post(f"{self.base_url}{path}", headers=headers, json=payload, timeout=self.timeout)
                if response.status_code in {408, 409, 429, 500, 502, 503, 504} and attempt < self.retries:
                    retry_after = response.headers.get("retry-after")
                    time.sleep(self._retry_delay(retry_after, attempt))
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                if self._not_retryable(exc):
                    raise MetaApiError(f"Meta API request failed: {self._describe(exc)}") from exc
                if attempt >= self.retries:
                    raise MetaApiError(f"Meta API request failed after retries: {self._describe(exc)}") from exc
        raise MetaApiError("Meta API request failed")


class MetaMuseSparkAdapter(_MetaBase):
    model = "muse-spark-1.3"

    def recommend_probes(self, scenario: Scenario) -> list[str]:
        payload = {
            "model": self.model,
            "instructions": "Return JSON only: {\"probes\":[short noun phrases]}. Choose at most 6 safety-relevant visual probes.",
            "input": f"Scene: {scenario.description}. Candidate probes: {scenario.probe_catalog}",
            "store": False,
        }
        data = self._post(payload)
        text = _output_text(data).strip()
        if text.startswith("```"):  # models often wrap JSON in a markdown fence
            text = text.strip("`").removeprefix("json").strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("planner reply was not valid JSON") from exc
        probes = [p for p in parsed.get("probes", []) if p in scenario.probe_catalog] if isinstance(parsed, dict) else []
        if not probes:
            raise ValueError("planner reply named no probes from the catalog")
        return probes

    def smoke_text(self) -> str:
        data = self._post({"model": self.model, "input": "Return the word READY.", "store": False})
        return _output_text(data)

    def inspect(self, scenario: Scenario, probe: str) -> ProviderResult:
        raise NotImplementedError("Use MetaSam31Adapter for visual segmentation; Muse Spark is probe planning here.")


class MetaSam31Adapter(_MetaBase):
    """Live SAM 3.1 segmentation through the Responses API.

    The request shape (a text prompt plus an input_image part) follows the Responses API but has
    not been confirmed against a live account here. Run `smoke-sam` once before relying on it.
    """

    model = "sam-3.1"
    stream = True  # Meta's SAM notes describe streaming responses; set BLINDSPOT_SAM_STREAM=0 to disable

    def inspect(self, scenario: Scenario, probe: str) -> ProviderResult:
        if not scenario.image_url:
            raise ValueError("SAM 3.1 live inspection needs scenario.image_url")
        if not is_allowed_image_url(scenario.image_url):
            raise ValueError("scenario.image_url must be a public https URL or a jpg/png/webp data URL")
        payload = {
            "model": self.model,
            "input": [{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": probe},
                {"type": "input_image", "image_url": scenario.image_url},
            ]}],
            "store": False,
        }
        data = self._post_stream(payload) if self.stream else self._post(payload)
        raw = _output_text(data)
        detections, status, notes = parse_sam_output(raw, probe, self.name)
        return ProviderResult(
            provider=self.name,
            model=self.model,
            detections=detections,
            raw_text=raw,
            usage=data.get("usage", {}),
            estimated_cost_usd=2.50 / 1000,
            parser_status=status,
            parser_notes=notes,
        )
