# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Local OpenAI-compatible typed-decision provider (Ollama / llama.cpp / vLLM).

Implements the DecisionProvider contract against a locally hosted
OpenAI-compatible chat-completions endpoint using the Python standard
library (urllib.request) with zero external dependencies.

Privacy posture (RFC-AI-0004 Principle 6):
- The endpoint must be a loopback host (plain HTTP is only allowed there),
  which the privacy-llm gate default-approves; any other host needs an
  explicit opt-in entry and HTTPS.
- Environment proxies (``HTTP_PROXY`` / ``HTTPS_PROXY``) are disabled for
  every request and redirects are rejected, so a loopback URL stays
  loopback for the whole round trip.
- All three operations fail open per the contract: any transport, schema,
  or validation failure raises ``TypedDecisionUnavailable`` — never a
  fabricated answer.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from checker.check import _LOCAL_HOSTS

from typed_decision.exceptions import TypedDecisionUnavailable
from typed_decision.interface import DecisionProvider
from typed_decision.privacy import enforce_privacy_gate

DEFAULT_LOCAL_ENDPOINT: str = "http://localhost:11434/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_BACKOFF_SECONDS: float = 0.5

LOCAL_ENDPOINT_ENV = "MAGPIE_TYPED_DECISION_LOCAL_ENDPOINT"
LOCAL_MODEL_ENV = "MAGPIE_TYPED_DECISION_LOCAL_MODEL"
LOCAL_API_KEY_ENV = "MAGPIE_TYPED_DECISION_LOCAL_API_KEY"

# The privacy gate's own loopback set, so the transport check and the gate
# cannot disagree about which hosts count as local-only.
_LOOPBACK_HOSTS = _LOCAL_HOSTS
_THINKING_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so a loopback request cannot be bounced to another host."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise TypedDecisionUnavailable(
            f"Request redirected to {newurl}; refusing to follow redirects for a local endpoint"
        )


def _require_https(url: str) -> None:
    """Ensure the URL uses HTTPS (permitting HTTP only for loopback hosts)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and (parsed.hostname or "").lower() in _LOOPBACK_HOSTS:
        return
    raise TypedDecisionUnavailable(
        f"Insecure endpoint URL: '{url}' must use HTTPS (plain HTTP is only allowed for loopback hosts)"
    )


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    """Extract a descriptive message from an HTTP error response."""
    try:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            for key in ("error", "message", "detail"):
                val = parsed.get(key)
                if val:
                    return str(val)
        return body.strip() or str(exc)
    except Exception:
        return str(exc.reason or exc)


def _is_timeout(exc: urllib.error.URLError) -> bool:
    """Check if URLError was caused by a connection or read timeout."""
    if isinstance(exc.reason, (socket.timeout, TimeoutError)):
        return True
    reason_str = str(exc.reason).lower()
    return "timed out" in reason_str or "timeout" in reason_str


def _require_finite_float(raw: Any, field: str) -> float:
    """Parse a strictly finite, non-bool numeric field or fail open."""
    if raw is None:
        raise TypedDecisionUnavailable(f"Local model response missing {field!r}")
    if isinstance(raw, bool):
        raise TypedDecisionUnavailable(
            f"Local model returned non-numeric {field} {raw!r}: boolean is not allowed"
        )
    try:
        value = float(raw)
    except (ValueError, TypeError) as exc:
        raise TypedDecisionUnavailable(f"Local model returned non-numeric {field} {raw!r}: {exc}") from exc
    if not math.isfinite(value):
        raise TypedDecisionUnavailable(f"Local model returned non-finite {field} {value!r}")
    return value


def _require_confidence(raw: Any) -> float:
    """Parse and range-check a confidence field in [0.0, 1.0]."""
    confidence = _require_finite_float(raw, "confidence")
    if not 0.0 <= confidence <= 1.0:
        raise TypedDecisionUnavailable(
            f"Local model returned confidence {confidence} outside valid range [0.0, 1.0]"
        )
    return confidence


def _normalize_scale(scale: tuple[float, float] | list[float] | int | float) -> tuple[float, float]:
    """Normalize a scale argument to a validated (min, max) pair."""
    if isinstance(scale, bool):
        raise TypedDecisionUnavailable(f"Invalid scale: bool ({scale!r}) is not a valid numeric scale")
    if isinstance(scale, (int, float)):
        try:
            s_max = float(scale)
        except (ValueError, TypeError) as exc:
            raise TypedDecisionUnavailable(f"Invalid scalar scale {scale!r}: {exc}") from exc
        if not math.isfinite(s_max) or s_max <= 0:
            raise TypedDecisionUnavailable(
                f"Invalid scalar scale: upper bound ({s_max}) must be finite and strictly positive"
            )
        return (0.0, s_max)
    if isinstance(scale, (tuple, list)):
        if len(scale) != 2:
            raise TypedDecisionUnavailable("scale must be a (min, max) pair of 2 values")
        if isinstance(scale[0], bool) or isinstance(scale[1], bool):
            raise TypedDecisionUnavailable("scale bounds must not be bool")
        try:
            s_min, s_max = float(scale[0]), float(scale[1])
        except (ValueError, TypeError) as exc:
            raise TypedDecisionUnavailable(f"Invalid scale values {scale!r}: {exc}") from exc
        if not (math.isfinite(s_min) and math.isfinite(s_max)):
            raise TypedDecisionUnavailable(
                f"Invalid scale: bounds must be finite numbers, got ({s_min}, {s_max})"
            )
        if s_min >= s_max:
            raise TypedDecisionUnavailable(
                f"Invalid scale: min ({s_min}) must be strictly less than max ({s_max})"
            )
        return (s_min, s_max)
    raise TypedDecisionUnavailable(f"Invalid scale type: {type(scale).__name__}")


def _decision_schema(operation: str, options: list[str] | None = None) -> dict[str, Any]:
    """Build the strict JSON schema constraining the model's decision output."""
    properties: dict[str, Any]
    if operation == "choice":
        properties = {
            "label": {"type": "string", "enum": list(options or [])},
            "confidence": {"type": "number"},
        }
    elif operation == "score":
        properties = {
            "value": {"type": "number"},
            "confidence": {"type": "number"},
        }
    else:
        properties = {"probability": {"type": "number"}}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }


def _extract_decision_object(resp: dict[str, Any]) -> dict[str, Any]:
    """Extract the decision JSON object from an OpenAI chat-completions response.

    Reads ``choices[0].message.content`` and parses it as JSON. Reasoning tags
    are removed, and JSON in a fenced block is extracted even when a runtime
    adds a preamble before it.
    """
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        raise TypedDecisionUnavailable(
            "Malformed response from local model endpoint: missing 'choices' array"
        )
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise TypedDecisionUnavailable("Malformed response from local model endpoint: empty message content")

    text = _THINKING_BLOCK_RE.sub("", content).strip()
    fenced_json = _FENCED_JSON_RE.search(text)
    if fenced_json:
        text = fenced_json.group(1)

    try:
        decision = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TypedDecisionUnavailable(
            f"Failed to parse JSON decision from local model response: {exc}"
        ) from exc
    if not isinstance(decision, dict):
        raise TypedDecisionUnavailable(
            "Malformed decision from local model endpoint: expected JSON object, "
            f"got {type(decision).__name__}"
        )
    return decision


class LocalProvider(DecisionProvider):
    """Typed-decision provider backed by a local OpenAI-compatible endpoint.

    Targets self-hosted runtimes that expose the OpenAI chat-completions wire
    format with structured-output support: Ollama (`:11434/v1`), llama.cpp
    server (`:8080/v1`), and vLLM (`:8000/v1`).
    """

    def __init__(
        self,
        model: str | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self._endpoint = endpoint or os.environ.get(LOCAL_ENDPOINT_ENV, "").strip() or DEFAULT_LOCAL_ENDPOINT
        self._model = (model or os.environ.get(LOCAL_MODEL_ENV, "")).strip()
        self._timeout_seconds = timeout_seconds
        self._backoff_seconds = backoff_seconds

        resolved_key = (api_key or os.environ.get(LOCAL_API_KEY_ENV, "")).strip()
        self._api_key = resolved_key or None

        if not self._model:
            raise TypedDecisionUnavailable(
                "Missing model for local provider: pass model= or set "
                f"{LOCAL_MODEL_ENV} (e.g. 'qwen3.5:9b' for Ollama)"
            )
        _require_https(self._endpoint)

    @property
    def name(self) -> str:
        return "local"

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def model(self) -> str:
        return self._model

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    def _build_opener(self) -> urllib.request.OpenerDirector:
        """Build an opener that never honors environment proxies or redirects.

        An explicit empty ``ProxyHandler`` replaces the default one so
        ``HTTP_PROXY`` / ``HTTPS_PROXY`` cannot route a loopback request
        through an unapproved hop.
        """
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirectHandler)

    def _execute_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP POST with single retry on timeout, fail-open on any error."""
        _require_https(self._endpoint)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self._endpoint, data=data, headers=headers, method="POST")
        opener = self._build_opener()
        max_retries = 1

        for attempt in range(max_retries + 1):
            try:
                with opener.open(req, timeout=self._timeout_seconds) as resp:
                    body = resp.read().decode("utf-8")
                    parsed = json.loads(body)
                    if not isinstance(parsed, dict):
                        raise TypedDecisionUnavailable(
                            "Malformed response from local model endpoint: expected JSON object, "
                            f"got {type(parsed).__name__}"
                        )
                    return parsed

            except TypedDecisionUnavailable:
                raise

            except TimeoutError as exc:
                if attempt < max_retries:
                    if self._backoff_seconds > 0:
                        time.sleep(self._backoff_seconds)
                    continue
                raise TypedDecisionUnavailable(
                    f"Request to local model endpoint timed out after retry ({self._timeout_seconds}s limit)"
                ) from exc

            except urllib.error.HTTPError as exc:
                msg = _read_http_error(exc)
                raise TypedDecisionUnavailable(
                    f"Local model endpoint returned HTTP {exc.code}: {msg}"
                ) from exc

            except urllib.error.URLError as exc:
                if _is_timeout(exc):
                    if attempt < max_retries:
                        if self._backoff_seconds > 0:
                            time.sleep(self._backoff_seconds)
                        continue
                    raise TypedDecisionUnavailable(
                        f"Request to local model endpoint timed out after retry ({self._timeout_seconds}s limit)"
                    ) from exc
                raise TypedDecisionUnavailable(
                    f"Failed to connect to local model endpoint: {exc.reason}"
                ) from exc

            except json.JSONDecodeError as exc:
                raise TypedDecisionUnavailable(
                    f"Failed to parse JSON response from local model endpoint: {exc}"
                ) from exc

            except Exception as exc:
                raise TypedDecisionUnavailable(
                    f"Unexpected error communicating with local model endpoint: {exc}"
                ) from exc

        raise TypedDecisionUnavailable("Request to local model endpoint failed after retry")

    def _chat_decision(
        self,
        prompt: str,
        operation: str,
        options: list[str] | None = None,
        task_instruction: str | None = None,
    ) -> dict[str, Any]:
        """Send one gated chat-completion request and extract the decision object.

        ``task_instruction`` carries the operation semantics (the option set
        for ``choice``, the scale bounds for ``score``) — a generic chat model
        has no structured operation field, so the instruction must travel in
        the message while the strict JSON schema constrains the shape.
        """
        # The gate is a destination check (it returns the prompt unchanged), but
        # the full outbound message content — prompt plus the appended task
        # instruction — is assembled first so the gate sees everything the
        # endpoint will receive.
        content = f"{prompt}\n\n{task_instruction}" if task_instruction else prompt
        vetted_content = enforce_privacy_gate(content, self._endpoint, provider_name="Local model")
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": vetted_content}],
            "temperature": 0.0,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"typed_decision_{operation}",
                    "strict": True,
                    "schema": _decision_schema(operation, options),
                },
            },
        }
        resp = self._execute_request(payload)
        return _extract_decision_object(resp)

    def choice(self, prompt: str, options: list[str]) -> dict[str, Any]:
        """Select a single option label from candidate options.

        Returns:
            {"label": str, "confidence": float}
        """
        if not options:
            raise TypedDecisionUnavailable("choice operation requires a non-empty list of options")

        instruction = (
            "Choose exactly one label from these options: "
            f"{json.dumps(list(options))}. Respond with a single JSON object "
            '{"label": <one of the options>, "confidence": <number between 0.0 and 1.0>}.'
        )
        decision = self._chat_decision(prompt, "choice", options, task_instruction=instruction)
        try:
            label = decision.get("label")
            if label is None:
                raise TypedDecisionUnavailable("Local model response missing 'label'")
            if isinstance(label, bool):
                raise TypedDecisionUnavailable(f"Local model returned boolean for 'label': {label!r}")
            label_str = str(label)
            if label_str not in options:
                raise TypedDecisionUnavailable(
                    f"Local model returned label {label_str!r} not in candidate options: {options}"
                )
            return {
                "label": label_str,
                "confidence": _require_confidence(decision.get("confidence")),
            }
        except TypedDecisionUnavailable:
            raise
        except Exception as exc:
            raise TypedDecisionUnavailable(f"Malformed response from local model endpoint: {exc}") from exc

    def score(
        self,
        prompt: str,
        scale: tuple[float, float] | list[float] | int | float,
    ) -> dict[str, Any]:
        """Evaluate a score for prompt along given scale.

        Returns:
            {"value": float | int, "confidence": float}
        """
        norm_scale = _normalize_scale(scale)
        instruction = (
            f"Assign a numeric score between {norm_scale[0]} and {norm_scale[1]}. "
            "Respond with a single JSON object "
            '{"value": <number within the scale>, "confidence": <number between 0.0 and 1.0>}.'
        )
        decision = self._chat_decision(prompt, "score", task_instruction=instruction)
        try:
            value = _require_finite_float(decision.get("value"), "value")
            if not norm_scale[0] <= value <= norm_scale[1]:
                raise TypedDecisionUnavailable(
                    f"Local model returned score {value} outside scale range "
                    f"[{norm_scale[0]}, {norm_scale[1]}]"
                )
            return {
                "value": value,
                "confidence": _require_confidence(decision.get("confidence")),
            }
        except TypedDecisionUnavailable:
            raise
        except Exception as exc:
            raise TypedDecisionUnavailable(f"Malformed response from local model endpoint: {exc}") from exc

    def noul(self, prompt: str) -> dict[str, Any]:
        """Evaluate null/binary decision probability.

        Returns:
            {"probability": float}
        """
        instruction = (
            "Estimate the probability that the proposition is true. Respond with a "
            'single JSON object {"probability": <number between 0.0 and 1.0>}.'
        )
        decision = self._chat_decision(prompt, "noul", task_instruction=instruction)
        try:
            probability = _require_finite_float(decision.get("probability"), "probability")
            if not 0.0 <= probability <= 1.0:
                raise TypedDecisionUnavailable(
                    f"Local model returned probability {probability} outside valid range [0.0, 1.0]"
                )
            return {"probability": probability}
        except TypedDecisionUnavailable:
            raise
        except Exception as exc:
            raise TypedDecisionUnavailable(f"Malformed response from local model endpoint: {exc}") from exc
