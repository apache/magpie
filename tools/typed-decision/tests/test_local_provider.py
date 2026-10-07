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

"""Unit tests for the local OpenAI-compatible typed-decision provider."""

from __future__ import annotations

import email.message
import io
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from typed_decision import LocalProvider, TypedDecisionUnavailable, get_provider
from typed_decision.providers.local import (
    DEFAULT_LOCAL_ENDPOINT,
    LOCAL_API_KEY_ENV,
    LOCAL_ENDPOINT_ENV,
    LOCAL_MODEL_ENV,
    NoRedirectHandler,
)


@pytest.fixture(autouse=True)
def clean_local_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep local-provider environment knobs and proxy variables out of tests."""
    for var in (
        LOCAL_ENDPOINT_ENV,
        LOCAL_MODEL_ENV,
        LOCAL_API_KEY_ENV,
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
    ):
        monkeypatch.delenv(var, raising=False)


def _make_mock_response(body: dict[str, Any] | str, status: int = 200) -> MagicMock:
    """Helper to produce a mock HTTP response object for urllib."""
    mock_resp = MagicMock()
    mock_resp.status = status
    if isinstance(body, dict):
        raw_bytes = json.dumps(body).encode("utf-8")
    else:
        raw_bytes = body.encode("utf-8")
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


def _chat_completion_response(content: str) -> MagicMock:
    """Wrap a message content string into an OpenAI chat-completions envelope."""
    return _make_mock_response({"choices": [{"message": {"role": "assistant", "content": content}}]})


# ---------------------------------------------------------------------------
# 1. Construction and Configuration
# ---------------------------------------------------------------------------


def test_local_missing_model_raises_unavailable() -> None:
    """Without a model name (arg or env), construction fails open."""
    with pytest.raises(TypedDecisionUnavailable, match="Missing model for local provider"):
        LocalProvider()


def test_local_explicit_model_succeeds() -> None:
    """Providing an explicit model succeeds and reports the 'local' name."""
    provider = LocalProvider(model="qwen3.5:9b")
    assert provider.name == "local"
    assert provider.model == "qwen3.5:9b"
    assert provider.endpoint == DEFAULT_LOCAL_ENDPOINT


def test_local_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting MAGPIE_TYPED_DECISION_LOCAL_MODEL provides the model."""
    monkeypatch.setenv(LOCAL_MODEL_ENV, "llama3.1:8b")
    provider = LocalProvider()
    assert provider.model == "llama3.1:8b"


def test_local_endpoint_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """MAGPIE_TYPED_DECISION_LOCAL_ENDPOINT overrides the default endpoint."""
    monkeypatch.setenv(LOCAL_MODEL_ENV, "m")
    monkeypatch.setenv(LOCAL_ENDPOINT_ENV, "http://127.0.0.1:8080/v1/chat/completions")
    provider = LocalProvider()
    assert provider.endpoint == "http://127.0.0.1:8080/v1/chat/completions"


def test_local_rejects_remote_http_endpoint() -> None:
    """Plain HTTP is only allowed for loopback hosts."""
    with pytest.raises(TypedDecisionUnavailable, match="must use HTTPS"):
        LocalProvider(model="m", endpoint="http://192.168.1.5:8000/v1/chat/completions")


def test_local_allows_loopback_http_and_any_https() -> None:
    """Loopback HTTP and arbitrary HTTPS endpoints pass the transport check."""
    LocalProvider(model="m", endpoint="http://localhost:11434/v1/chat/completions")
    LocalProvider(model="m", endpoint="http://LOCALHOST:11434/v1/chat/completions")
    LocalProvider(model="m", endpoint="http://127.0.0.1:8080/v1/chat/completions")
    LocalProvider(model="m", endpoint="https://127.0.0.1:8080/v1/chat/completions")


def test_local_optional_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """An optional API key is resolved from the environment and sent as Bearer."""
    monkeypatch.setenv(LOCAL_API_KEY_ENV, "local-secret")
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"probability": 0.5}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        provider.noul("Is this actionable?")
        req: urllib.request.Request = mock_open.call_args[0][0]
        assert req.headers["Authorization"] == "Bearer local-secret"

    monkeypatch.delenv(LOCAL_API_KEY_ENV)
    unauth_provider = LocalProvider(model="m")
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        unauth_provider.noul("Is this actionable?")
        req = mock_open.call_args[0][0]
        assert "Authorization" not in req.headers


# ---------------------------------------------------------------------------
# 2. Privacy Gate
# ---------------------------------------------------------------------------


def test_local_loopback_default_approved_without_config() -> None:
    """Loopback endpoints are default-approved: no privacy-llm.md needed."""
    provider = LocalProvider(model="qwen3.5:9b")
    mock_resp = _chat_completion_response('{"label": "bug", "confidence": 0.9}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        assert provider.choice("Classify this", ["bug", "feature"]) == {
            "label": "bug",
            "confidence": 0.9,
        }


def test_local_remote_https_endpoint_denied_by_default() -> None:
    """A non-loopback HTTPS endpoint needs an explicit opt-in: denied by default."""
    provider = LocalProvider(model="m", endpoint="https://gpu.internal.example:8000/v1/chat/completions")
    with patch("urllib.request.OpenerDirector.open") as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="Privacy-LLM gate rejected"):
            provider.noul("Is this actionable?")
        mock_open.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Success Paths and Request Shape
# ---------------------------------------------------------------------------


def test_local_choice_request_shape_and_result() -> None:
    """choice sends a strict json_schema request carrying the option set."""
    provider = LocalProvider(model="qwen3.5:9b")
    mock_resp = _chat_completion_response('{"label": "bug", "confidence": 0.96}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        result = provider.choice("Classify issue description", ["bug", "feature", "question"])

        assert result == {"label": "bug", "confidence": 0.96}
        req: urllib.request.Request = mock_open.call_args[0][0]
        assert req.full_url == DEFAULT_LOCAL_ENDPOINT
        assert req.headers["Content-type"] == "application/json"

        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        assert body["model"] == "qwen3.5:9b"
        assert body["temperature"] == 0.0
        assert body["stream"] is False
        assert "Classify issue description" in body["messages"][0]["content"]
        assert json.dumps(["bug", "feature", "question"]) in body["messages"][0]["content"]

        response_format = body["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        schema = response_format["json_schema"]["schema"]
        assert schema["properties"]["label"]["enum"] == ["bug", "feature", "question"]
        assert schema["required"] == ["label", "confidence"]
        assert schema["additionalProperties"] is False


def test_local_choice_accepts_fenced_content() -> None:
    """Content fenced in markdown code blocks is unwrapped before parsing."""
    provider = LocalProvider(model="m")
    fenced = '```json\n{"label": "feature", "confidence": 0.7}\n```'
    mock_resp = _chat_completion_response(fenced)
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        assert provider.choice("Classify this", ["bug", "feature"]) == {
            "label": "feature",
            "confidence": 0.7,
        }


def test_local_choice_accepts_reasoning_preamble_before_fence() -> None:
    """Reasoning tags and prose before a fenced JSON decision are ignored."""
    provider = LocalProvider(model="m")
    content = (
        "<think>Consider the available labels.</think>\n"
        "Here is the decision:\n"
        '```json\n{"label": "feature", "confidence": 0.7}\n```'
    )
    mock_resp = _chat_completion_response(content)
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        assert provider.choice("Classify this", ["bug", "feature"]) == {
            "label": "feature",
            "confidence": 0.7,
        }


def test_local_score_success_carries_scale_in_instruction() -> None:
    """score embeds the scale bounds in the message and validates the value."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"value": 4.5, "confidence": 0.89}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        result = provider.score("Rate severity of vulnerability", scale=(1, 5))

        assert result == {"value": 4.5, "confidence": 0.89}
        req_data = mock_open.call_args[0][0].data
        assert isinstance(req_data, bytes)
        body = json.loads(req_data.decode("utf-8"))
        assert "between 1.0 and 5.0" in body["messages"][0]["content"]
        schema = body["response_format"]["json_schema"]["schema"]
        assert schema["required"] == ["value", "confidence"]


def test_local_score_accepts_scalar_scale() -> None:
    """A scalar upper bound normalizes to (0, max)."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"value": 3, "confidence": 0.5}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        assert provider.score("Rate this", scale=10) == {"value": 3.0, "confidence": 0.5}


def test_local_noul_success() -> None:
    """noul returns the model's probability."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"probability": 0.78}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        assert provider.noul("Is this report actionable?") == {"probability": 0.78}


# ---------------------------------------------------------------------------
# 4. Validation Failures (Fail-Open)
# ---------------------------------------------------------------------------


def test_local_choice_empty_options_raises() -> None:
    """choice requires a non-empty option list."""
    provider = LocalProvider(model="m")
    with pytest.raises(TypedDecisionUnavailable, match="non-empty"):
        provider.choice("Test", [])


def test_local_choice_rejects_label_not_in_options() -> None:
    """A label outside the candidate options fails open."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"label": "spicy", "confidence": 0.9}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="not in candidate options"):
            provider.choice("Test", ["bug", "feature"])


def test_local_choice_rejects_boolean_label() -> None:
    """A boolean label fails open."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"label": true, "confidence": 0.9}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="boolean"):
            provider.choice("Test", ["True", "False"])


def test_local_choice_rejects_invalid_confidence() -> None:
    """Confidence outside [0.0, 1.0] or non-numeric fails open."""
    provider = LocalProvider(model="m")
    for content in ('{"label": "bug", "confidence": 1.5}', '{"label": "bug", "confidence": true}'):
        mock_resp = _chat_completion_response(content)
        with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
            with pytest.raises(TypedDecisionUnavailable):
                provider.choice("Test", ["bug", "feature"])


def test_local_score_rejects_value_outside_scale() -> None:
    """A value outside the normalized scale fails open."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"value": 7.0, "confidence": 0.9}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="outside scale range"):
            provider.score("Rate this", scale=(1, 5))


def test_local_score_rejects_non_finite_value() -> None:
    """NaN / Infinity in the decision JSON fails open."""
    provider = LocalProvider(model="m")
    for raw in ('{"value": NaN, "confidence": 0.9}', '{"value": Infinity, "confidence": 0.9}'):
        mock_resp = _chat_completion_response(raw)
        with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
            with pytest.raises(TypedDecisionUnavailable, match="non-finite"):
                provider.score("Rate this", scale=(1, 5))


def test_local_score_rejects_invalid_scale() -> None:
    """Invalid scale arguments fail fast before any request."""
    provider = LocalProvider(model="m")
    bad_scales: list[Any] = [(5, 1), (1, 2, 3), True, "high"]
    for scale in bad_scales:
        with pytest.raises(TypedDecisionUnavailable):
            provider.score("Rate this", scale=scale)


def test_local_noul_rejects_probability_out_of_range() -> None:
    """A probability outside [0.0, 1.0] fails open."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"probability": 1.2}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="outside valid range"):
            provider.noul("Is this actionable?")


def test_local_non_object_decision_fails_open() -> None:
    """A decision that parses to a non-object fails open."""
    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response("[1, 2, 3]")
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="expected JSON object"):
            provider.noul("Is this actionable?")


def test_local_malformed_envelope_fails_open() -> None:
    """Missing choices, empty content, and non-JSON content all fail open."""
    provider = LocalProvider(model="m")
    envelopes = (
        '{"choices": []}',
        '{"choices": [{"message": {"role": "assistant", "content": ""}}]}',
        '{"choices": [{"message": {"role": "assistant", "content": "not json at all"}}]}',
        '{"error": "no choices here"}',
    )
    for raw in envelopes:
        mock_resp = _make_mock_response(raw)
        with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
            with pytest.raises(TypedDecisionUnavailable):
                provider.noul("Is this actionable?")


# ---------------------------------------------------------------------------
# 5. Transport Failures (Fail-Open)
# ---------------------------------------------------------------------------


def test_local_http_error_fail_open() -> None:
    """An HTTP 4xx/5xx response (e.g. response_format unsupported) fails open."""
    provider = LocalProvider(model="m")
    headers = email.message.Message()
    error = urllib.error.HTTPError(
        provider.endpoint,
        400,
        "Bad Request",
        headers,
        io.BytesIO(b'{"error": "response_format unsupported"}'),
    )
    with patch("urllib.request.OpenerDirector.open", side_effect=error):
        with pytest.raises(TypedDecisionUnavailable, match="HTTP 400"):
            provider.noul("Is this actionable?")


def test_local_timeout_retries_once_then_unavailable() -> None:
    """A timeout is retried exactly once before failing open."""
    provider = LocalProvider(model="m", backoff_seconds=0.0)
    with patch("urllib.request.OpenerDirector.open", side_effect=TimeoutError()) as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="timed out after retry"):
            provider.noul("Is this actionable?")
        assert mock_open.call_count == 2


def test_local_timeout_first_attempt_retry_succeeds() -> None:
    """A request that succeeds on retry returns normally."""
    provider = LocalProvider(model="m", backoff_seconds=0.0)
    mock_resp = _chat_completion_response('{"probability": 0.4}')
    with patch("urllib.request.OpenerDirector.open", side_effect=[TimeoutError(), mock_resp]) as mock_open:
        assert provider.noul("Is this actionable?") == {"probability": 0.4}
        assert mock_open.call_count == 2


def test_local_connection_error_fail_open() -> None:
    """A connection failure fails open with the underlying reason."""
    provider = LocalProvider(model="m")
    with patch(
        "urllib.request.OpenerDirector.open",
        side_effect=urllib.error.URLError(ConnectionRefusedError()),
    ):
        with pytest.raises(TypedDecisionUnavailable, match="Failed to connect"):
            provider.noul("Is this actionable?")


def test_no_redirect_handler_blocks_redirects() -> None:
    """Redirects are rejected so a loopback request cannot be bounced elsewhere."""
    handler = NoRedirectHandler()
    req = urllib.request.Request(DEFAULT_LOCAL_ENDPOINT)
    with pytest.raises(TypedDecisionUnavailable, match="refusing to follow redirects"):
        handler.redirect_request(req, None, 302, "Found", {}, "http://attacker.example.com/exfil")


def test_local_opener_disables_environment_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    """The opener never honors HTTP(S)_PROXY: a loopback request stays loopback.

    An explicit empty ``ProxyHandler({})`` makes ``build_opener`` skip the
    default environment-derived handler, and an empty proxy map contributes no
    ``<type>_open`` methods of its own — so the opener contains no proxy
    handler at all and requests always go direct.
    """
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.com:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.com:3128")
    provider = LocalProvider(model="m")
    opener = provider._build_opener()
    handlers: list[Any] = list(getattr(opener, "handlers"))
    proxy_handlers = [h for h in handlers if isinstance(h, urllib.request.ProxyHandler)]
    assert proxy_handlers == []


def test_local_request_bypasses_proxy_and_rejects_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: with proxies configured, the request lands on the loopback
    server directly, and its 302 to a non-loopback host is rejected instead of
    being followed — the exact regression named in #1431's review discussion.
    """
    received_paths: list[str] = []

    class _RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            received_paths.append(self.path)
            self.send_response(302)
            self.send_header("Location", "http://attacker.example.com/exfil")
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # A dead proxy: if the opener honored it, the request could not land here.
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
        provider = LocalProvider(
            model="m", endpoint=f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        )
        with pytest.raises(TypedDecisionUnavailable, match="refusing to follow redirects"):
            provider.noul("Is this actionable?")
        assert received_paths == ["/v1/chat/completions"]
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# 6. Registry Integration
# ---------------------------------------------------------------------------


def test_registry_local_selected_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """MAGPIE_TYPED_DECISION_PROVIDER=local resolves the local provider."""
    monkeypatch.setenv("MAGPIE_TYPED_DECISION_PROVIDER", "local")
    monkeypatch.setenv(LOCAL_MODEL_ENV, "qwen3.5:9b")
    provider = get_provider()
    assert isinstance(provider, LocalProvider)
    assert provider.model == "qwen3.5:9b"


def test_registry_local_without_model_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting 'local' without a configured model fails open."""
    monkeypatch.setenv("MAGPIE_TYPED_DECISION_PROVIDER", "local")
    with pytest.raises(TypedDecisionUnavailable, match="Missing model"):
        get_provider()


def test_functional_api_with_explicit_local_provider() -> None:
    """The functional API accepts an explicit LocalProvider instance."""
    from typed_decision import choice

    provider = LocalProvider(model="m")
    mock_resp = _chat_completion_response('{"label": "question", "confidence": 0.6}')
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        assert choice("Classify this", ["bug", "question"], provider=provider) == {
            "label": "question",
            "confidence": 0.6,
        }
