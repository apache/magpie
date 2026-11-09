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

"""TypeSafe Jev (SystemOne) typed-decision provider implementation.

Implements the DecisionProvider contract against api.typesafe.ai/v1/systemone
using the Python standard library (urllib.request) with zero external dependencies.
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from typed_decision.exceptions import TypedDecisionUnavailable
from typed_decision.interface import DecisionProvider
from typed_decision.privacy import DEFAULT_ENDPOINT, enforce_privacy_gate

# The model version is strictly pinned to an immutable release snapshot, never "latest"
# (per RFC-AI-0004 § Principle 3: Vendor neutrality & reproducible evaluations).
JEV_MODEL: str = "jev-1.14.0"
# Every request asks one question; the API keys its answer by this name.
QUESTION_NAME: str = "decision"
# The API caps a Score question's criteria at this many levels.
MAX_SCORE_LEVELS: int = 10
DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_BACKOFF_SECONDS: float = 0.5


class NoAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so Authorization credentials are not forwarded to other origins."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise TypedDecisionUnavailable(f"Request redirected to {newurl}; refusing to forward credentials")


def _require_https(url: str) -> None:
    """Ensure the URL uses HTTPS (permitting HTTP only for localhost in tests)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return
    raise TypedDecisionUnavailable(f"Insecure endpoint URL: '{url}' must use HTTPS")


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


def _resolve_api_key(explicit_key: str | None = None) -> str | None:
    """Resolve API key from explicit arg, environment variables, or user home config."""
    if explicit_key:
        return explicit_key.strip()

    # Adopter environment variables
    for var_name in ("TYPESAFE_API_KEY", "JEV_API_KEY"):
        val = os.environ.get(var_name)
        if val and val.strip():
            return val.strip()

    # Home directory config fallback (~/.config/apache-magpie/typesafe.key)
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if home:
        key_paths = (
            pathlib.Path(home) / ".config" / "apache-magpie" / "typesafe.key",
            pathlib.Path(home) / ".config" / "apache-magpie" / "jev.key",
        )
        for kp in key_paths:
            if kp.is_file():
                try:
                    content = kp.read_text(encoding="utf-8").strip()
                    if content:
                        return content
                except OSError:
                    # Ignore unreadable or inaccessible key files and try next candidate path.
                    pass

    return None


def _extract_answer(resp: dict[str, Any], answer_type: str) -> dict[str, Any]:
    """Return the answer of the expected type from a System One response."""
    answers = resp.get("answers")
    if not isinstance(answers, dict):
        raise TypedDecisionUnavailable("Malformed response from Jev API: missing 'answers' object")
    answer = answers.get(QUESTION_NAME)
    if not isinstance(answer, dict) or answer.get("type") != answer_type:
        raise TypedDecisionUnavailable(f"Malformed response from Jev API: missing '{answer_type}' answer")
    return answer


def _build_score_levels(low: float, high: float) -> list[float]:
    """Spread numeric levels evenly across a scale, within the API's level cap."""
    span = high - low
    count = int(span) + 1 if span.is_integer() and span < MAX_SCORE_LEVELS else MAX_SCORE_LEVELS
    return [low + span * index / (count - 1) for index in range(count)]


class JevProvider(DecisionProvider):
    """TypeSafe Jev decision provider calling api.typesafe.ai/v1/systemone."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = JEV_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self._endpoint = endpoint
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._backoff_seconds = backoff_seconds

        resolved_key = _resolve_api_key(api_key)
        if not resolved_key:
            raise TypedDecisionUnavailable(
                "Missing API key for Jev provider: neither TYPESAFE_API_KEY nor JEV_API_KEY is configured"
            )
        self._api_key = resolved_key

    @property
    def name(self) -> str:
        return "jev"

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def model(self) -> str:
        return self._model

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    @property
    def backoff_seconds(self) -> float:
        return self._backoff_seconds

    def _build_payload(self, state: str, question: dict[str, Any]) -> dict[str, Any]:
        """Build a System One request; the prompt stays in state so it is read as data."""
        return {"model": self._model, "state": state, "questions": {QUESTION_NAME: question}}

    def _execute_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP POST with single retry on timeout, fail-open on any error."""
        _require_https(self._endpoint)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        opener = urllib.request.build_opener(NoAuthRedirectHandler)
        max_retries = 1

        for attempt in range(max_retries + 1):
            try:
                with opener.open(req, timeout=self._timeout_seconds) as resp:
                    body = resp.read().decode("utf-8")
                    parsed = json.loads(body)
                    if not isinstance(parsed, dict):
                        raise TypedDecisionUnavailable(
                            f"Malformed response from Jev API: expected JSON object, got {type(parsed).__name__}"
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
                    f"Request to Jev API timed out after retry ({self._timeout_seconds}s limit)"
                ) from exc

            except urllib.error.HTTPError as exc:
                msg = _read_http_error(exc)
                raise TypedDecisionUnavailable(f"Jev API returned HTTP {exc.code}: {msg}") from exc

            except urllib.error.URLError as exc:
                if _is_timeout(exc):
                    if attempt < max_retries:
                        if self._backoff_seconds > 0:
                            time.sleep(self._backoff_seconds)
                        continue
                    raise TypedDecisionUnavailable(
                        f"Request to Jev API timed out after retry ({self._timeout_seconds}s limit)"
                    ) from exc
                raise TypedDecisionUnavailable(f"Failed to connect to Jev API: {exc.reason}") from exc

            except json.JSONDecodeError as exc:
                raise TypedDecisionUnavailable(f"Failed to parse JSON response from Jev API: {exc}") from exc

            except Exception as exc:
                raise TypedDecisionUnavailable(f"Unexpected error communicating with Jev API: {exc}") from exc

        raise TypedDecisionUnavailable("Request to Jev API failed after retry")

    def choice(self, prompt: str, options: list[str]) -> dict[str, Any]:
        """Select a single option label from candidate options.

        Returns:
            {"label": str, "confidence": float}
        """
        if not options:
            raise TypedDecisionUnavailable("choice operation requires a non-empty list of options")

        vetted_prompt = enforce_privacy_gate(prompt, self._endpoint, provider_name="TypeSafe Jev")
        payload = self._build_payload(
            vetted_prompt,
            {
                "type": "choice",
                "instructions": "Select the option that best fits the state.",
                "criteria": {option: option for option in options},
            },
        )

        resp = self._execute_request(payload)

        try:
            if not isinstance(resp, dict):
                raise TypedDecisionUnavailable(
                    f"Malformed response from Jev API: expected JSON object, got {type(resp).__name__}"
                )

            result = _extract_answer(resp, "choice")

            label = result.get("choice")
            if label is None:
                raise TypedDecisionUnavailable("Jev API response missing 'choice'")
            if isinstance(label, bool):
                raise TypedDecisionUnavailable(f"Jev API returned boolean for 'choice': {label!r}")
            label_str = str(label)
            if label_str not in options:
                raise TypedDecisionUnavailable(
                    f"Jev API returned label {label_str!r} not in candidate options: {options}"
                )

            raw_conf = result.get("confidence")
            if raw_conf is None:
                raise TypedDecisionUnavailable("Jev API response missing 'confidence'")
            if isinstance(raw_conf, bool):
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric confidence {raw_conf!r}: boolean is not allowed"
                )
            try:
                confidence = float(raw_conf)
            except (ValueError, TypeError) as exc:
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric confidence {raw_conf!r}: {exc}"
                ) from exc

            if not 0.0 <= confidence <= 1.0:
                raise TypedDecisionUnavailable(
                    f"Jev API returned confidence {confidence} outside valid range [0.0, 1.0]"
                )

            return {
                "label": label_str,
                "confidence": confidence,
            }
        except TypedDecisionUnavailable:
            raise
        except Exception as exc:
            raise TypedDecisionUnavailable(f"Malformed response from Jev API: {exc}") from exc

    def score(
        self,
        prompt: str,
        scale: tuple[float, float] | list[float] | int | float,
    ) -> dict[str, Any]:
        """Evaluate a score for prompt along given scale.

        Returns:
            {"value": float | int, "confidence": float}
        """
        norm_scale: tuple[float, float]
        if isinstance(scale, bool):
            raise TypedDecisionUnavailable(f"Invalid scale: bool ({scale!r}) is not a valid numeric scale")
        elif isinstance(scale, (int, float)):
            try:
                s_max = float(scale)
                if not math.isfinite(s_max) or s_max <= 0:
                    raise TypedDecisionUnavailable(
                        f"Invalid scalar scale: upper bound ({s_max}) must be finite and strictly positive"
                    )
                norm_scale = (0.0, s_max)
            except (ValueError, TypeError) as exc:
                raise TypedDecisionUnavailable(f"Invalid scalar scale {scale!r}: {exc}") from exc
        elif isinstance(scale, (tuple, list)):
            if len(scale) != 2:
                raise TypedDecisionUnavailable("scale must be a (min, max) pair of 2 values")
            if isinstance(scale[0], bool) or isinstance(scale[1], bool):
                raise TypedDecisionUnavailable("scale bounds must not be bool")
            try:
                s_min, s_max = float(scale[0]), float(scale[1])
                if not (math.isfinite(s_min) and math.isfinite(s_max)):
                    raise TypedDecisionUnavailable(
                        f"Invalid scale: bounds must be finite numbers, got ({s_min}, {s_max})"
                    )
                if s_min >= s_max:
                    raise TypedDecisionUnavailable(
                        f"Invalid scale: min ({s_min}) must be strictly less than max ({s_max})"
                    )
                norm_scale = (s_min, s_max)
            except (ValueError, TypeError) as exc:
                raise TypedDecisionUnavailable(f"Invalid scale values {scale!r}: {exc}") from exc
        else:
            raise TypedDecisionUnavailable(f"Invalid scale type: {type(scale).__name__}")

        levels = _build_score_levels(norm_scale[0], norm_scale[1])
        labels = [f"{level:.15g}" for level in levels]
        if len(set(labels)) != len(labels):
            raise TypedDecisionUnavailable(
                f"Invalid scale: levels for {norm_scale} are not distinguishable as distinct labels"
            )
        vetted_prompt = enforce_privacy_gate(prompt, self._endpoint, provider_name="TypeSafe Jev")
        payload = self._build_payload(
            vetted_prompt,
            {
                "type": "score",
                "instructions": "Rate the state on this numeric scale. Each level is a score, lowest first.",
                "criteria": labels,
            },
        )

        resp = self._execute_request(payload)

        try:
            if not isinstance(resp, dict):
                raise TypedDecisionUnavailable(
                    f"Malformed response from Jev API: expected JSON object, got {type(resp).__name__}"
                )

            result = _extract_answer(resp, "score")

            raw_val = result.get("score")
            if raw_val is None:
                raise TypedDecisionUnavailable("Jev API response missing 'score'")
            if isinstance(raw_val, bool):
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric score value {raw_val!r}: boolean is not allowed"
                )
            try:
                position = float(raw_val)
            except (ValueError, TypeError) as exc:
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric score value {raw_val!r}: {exc}"
                ) from exc

            # The API scores by level position, starting at zero, so map it back onto the scale.
            last_level = len(levels) - 1
            if not math.isfinite(position) or not 0 <= position <= last_level:
                raise TypedDecisionUnavailable(
                    f"Jev API returned level position {position} outside [0, {last_level}] for scale {norm_scale}"
                )
            span = norm_scale[1] - norm_scale[0]
            value = min(norm_scale[1], norm_scale[0] + span * position / last_level)

            raw_conf = result.get("confidence")
            if raw_conf is None:
                raise TypedDecisionUnavailable("Jev API response missing 'confidence'")
            if isinstance(raw_conf, bool):
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric confidence {raw_conf!r}: boolean is not allowed"
                )
            try:
                confidence = float(raw_conf)
            except (ValueError, TypeError) as exc:
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric confidence {raw_conf!r}: {exc}"
                ) from exc

            if not 0.0 <= confidence <= 1.0:
                raise TypedDecisionUnavailable(
                    f"Jev API returned confidence {confidence} outside valid range [0.0, 1.0]"
                )

            return {
                "value": value,
                "confidence": confidence,
            }
        except TypedDecisionUnavailable:
            raise
        except Exception as exc:
            raise TypedDecisionUnavailable(f"Malformed response from Jev API: {exc}") from exc

    def noul(self, prompt: str) -> dict[str, Any]:
        """Evaluate null/binary decision probability.

        Returns:
            {"probability": float}
        """
        vetted_prompt = enforce_privacy_gate(prompt, self._endpoint, provider_name="TypeSafe Jev")
        payload = self._build_payload(
            vetted_prompt,
            {
                "type": "noul",
                "instructions": "Answer the yes/no question, or evaluate the statement, in the state.",
            },
        )

        resp = self._execute_request(payload)

        try:
            if not isinstance(resp, dict):
                raise TypedDecisionUnavailable(
                    f"Malformed response from Jev API: expected JSON object, got {type(resp).__name__}"
                )

            result = _extract_answer(resp, "noul")

            raw_prob = result.get("noul")
            if raw_prob is None:
                raise TypedDecisionUnavailable("Jev API response missing 'noul'")
            if isinstance(raw_prob, bool):
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric probability {raw_prob!r}: boolean is not allowed"
                )
            try:
                probability = float(raw_prob)
            except (ValueError, TypeError) as exc:
                raise TypedDecisionUnavailable(
                    f"Jev API returned non-numeric probability {raw_prob!r}: {exc}"
                ) from exc

            if not 0.0 <= probability <= 1.0:
                raise TypedDecisionUnavailable(
                    f"Jev API returned probability {probability} outside valid range [0.0, 1.0]"
                )

            return {
                "probability": probability,
            }
        except TypedDecisionUnavailable:
            raise
        except Exception as exc:
            raise TypedDecisionUnavailable(f"Malformed response from Jev API: {exc}") from exc
