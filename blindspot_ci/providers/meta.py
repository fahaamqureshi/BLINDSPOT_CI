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


SAM_IMAGE_COST_USD = 2.50 / 1000  # pricing page: SAM image segmentation is $2.50 per 1,000 images


def _output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    output = payload.get("output", [])
    if not isinstance(output, list):
        raise MetaApiError("Meta API reply had a malformed output list")
    for item in output:
        if not isinstance(item, dict):
            continue
        content_list = item.get("content", [])
        if not isinstance(content_list, list):
            continue
        for content in content_list:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise MetaApiError("Meta API reply was a refusal")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks)


def _strip_json_fence(text: str) -> str:
    """Remove one markdown code fence around a JSON reply, if the model added one."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    body = lines[1:] if lines else []
    if body and body[-1].strip() == "```":
        body = body[:-1]
    return "\n".join(body).strip()


class _MetaBase:
    name = "meta"

    def __init__(self, api_key: str, base_url: str = "https://api.meta.ai/v1", timeout: float = 45.0, retries: int = 2):
        if not api_key:
            raise ValueError("MODEL_API_KEY is required for the live Meta adapter")
        if not (0 < timeout <= 600):
            raise ValueError("timeout must be between 0 and 600 seconds")
        if not (0 <= retries <= 5):
            raise ValueError("retries must be between 0 and 5, so a paid call stays bounded")
        self.api_key, self.base_url, self.timeout, self.retries = api_key, base_url.rstrip("/"), timeout, retries

    def _check_response_status(self, payload: dict[str, Any]) -> None:
        """A synchronous reply that did not complete is an error, never an empty result."""
        status = payload.get("status")
        if status is None or status == "completed":
            return
        detail = payload.get("error") or payload.get("incomplete_details") or status
        text = json.dumps(detail)[:300].replace(self.api_key, "[redacted]")
        raise MetaApiError(f"Meta API response did not complete (status {status}): {text}")

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
                        time.sleep(self._retry_delay(response.headers.get("retry-after"), attempt))
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
        completed = False
        for line in lines:
            if not isinstance(line, str) or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError as exc:
                raise MetaApiError("Meta API stream sent a malformed event") from exc
            if not isinstance(event, dict):
                raise MetaApiError("Meta API stream sent a malformed event")
            kind = event.get("type", "")
            lane = (event.get("output_index", 0), event.get("content_index", 0))
            if kind == "response.output_text.delta":
                if not isinstance(event.get("delta", ""), str):
                    raise MetaApiError("Meta API stream sent a malformed text delta")
                deltas.setdefault(lane, []).append(event.get("delta", ""))
            elif kind == "response.output_text.done":
                if isinstance(event.get("text"), str):
                    lanes[lane] = event["text"]
            elif kind == "response.content_part.done" and isinstance(event.get("part"), dict) \
                    and event["part"].get("type") == "output_text":
                if isinstance(event["part"].get("text"), str):
                    lanes[lane] = event["part"]["text"]
            elif kind in {"response.refusal.delta", "response.refusal.done"} or (
                    kind == "response.content_part.done" and isinstance(event.get("part"), dict)
                    and event["part"].get("type") == "refusal"):
                raise MetaApiError("Meta API reply was a refusal")
            elif kind == "response.completed":
                completed = True
                response_obj = event.get("response") if isinstance(event.get("response"), dict) else {}
                usage = response_obj.get("usage", {}) or {}
            elif kind == "response.incomplete":
                response_obj = event.get("response") if isinstance(event.get("response"), dict) else {}
                detail = json.dumps(response_obj.get("incomplete_details") or response_obj)[:300]
                raise MetaApiError(
                    f"Meta API stream ended incomplete: {detail.replace(self.api_key, '[redacted]')}")
            elif kind in {"response.failed", "error"}:
                response_obj = event.get("response") if isinstance(event.get("response"), dict) else {}
                detail = json.dumps(response_obj.get("error") or event.get("error") or event)[:300]
                raise MetaApiError(f"Meta API stream failed: {detail.replace(self.api_key, '[redacted]')}")
        if not completed:
            # Docs: a valid empty SAM result still ends with response.completed. Without that
            # event the text is a truncated prefix, so it must not parse as a no-match.
            raise MetaApiError("Meta API stream ended before response.completed")
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
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise MetaApiError("Meta API reply was not valid JSON") from exc
                if not isinstance(payload, dict):
                    raise MetaApiError("Meta API reply was not a JSON object")
                if payload.get("error"):
                    detail = json.dumps(payload["error"])[:300].replace(self.api_key, "[redacted]")
                    raise MetaApiError(f"Meta API reply carried an error: {detail}")
                return payload
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
        self._check_response_status(data)
        text = _strip_json_fence(_output_text(data))
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("planner reply was not valid JSON") from exc
        raw_probes = parsed.get("probes") if isinstance(parsed, dict) else None
        if not isinstance(raw_probes, list):
            raise ValueError("planner reply named no probes from the catalog")  # noqa: TRY004 - callers treat a bad reply as ValueError
        probes: list[str] = []
        for probe in raw_probes:  # keep catalog order from the model, drop repeats
            if probe in scenario.probe_catalog and probe not in probes:
                probes.append(probe)
        if not probes:
            raise ValueError("planner reply named no probes from the catalog")
        return probes

    def smoke_text(self) -> str:
        data = self._post({"model": self.model, "input": "Return the word READY.", "store": False})
        self._check_response_status(data)
        text = _output_text(data)
        if not text.strip():
            raise MetaApiError("Muse Spark reply was empty")
        return text

    def inspect(self, scenario: Scenario, probe: str) -> ProviderResult:
        raise NotImplementedError("Use MetaSam31Adapter for visual segmentation; Muse Spark is probe planning here.")


class MetaSam31Adapter(_MetaBase):
    """Live SAM 3.1 segmentation through the Responses API.

    The request shape (a text prompt plus an input_image part) follows the Responses API but has
    not been confirmed against a live account here. Run `smoke-sam` once before relying on it.
    """

    model = "sam-3.1"
    stream = True  # Meta's SAM notes describe streaming responses; set BLINDSPOT_SAM_STREAM=0 to disable

    @staticmethod
    def _concept(probe: str) -> str:
        """One request names one concept: a short noun phrase, never a list or box tokens."""
        concept = probe.strip() if isinstance(probe, str) else ""
        if not concept:
            raise ValueError("SAM 3.1 probe must name one concept")
        if concept.startswith("<") or any(ch in concept for ch in ",;\n\r+"):
            raise ValueError("SAM 3.1 probe must name one concept in a single noun phrase")
        if len(concept) > 120:
            raise ValueError("SAM 3.1 probe must be a short noun phrase")
        return concept

    def inspect(self, scenario: Scenario, probe: str) -> ProviderResult:
        if not scenario.image_url:
            raise ValueError("SAM 3.1 live inspection needs scenario.image_url")
        if not is_allowed_image_url(scenario.image_url):
            raise ValueError("scenario.image_url must be a public https URL or a jpg/png/webp data URL")
        concept = self._concept(probe)
        payload = {
            "model": self.model,
            "input": [{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": concept},
                {"type": "input_image", "image_url": scenario.image_url},
            ]}],
            "store": False,
        }
        data = self._post_stream(payload) if self.stream else self._post(payload)
        self._check_response_status(data)
        raw = _output_text(data)
        detections, status, notes = parse_sam_output(raw, concept, self.name)
        return ProviderResult(
            provider=self.name,
            model=self.model,
            detections=detections,
            raw_text=raw,
            usage=data.get("usage", {}),
            estimated_cost_usd=SAM_IMAGE_COST_USD,
            parser_status=status,
            parser_notes=notes,
        )
