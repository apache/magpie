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

"""Unit tests for the typed-decision tool contract, Jev provider, and privacy gate."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from typed_decision import (
    DecisionProvider,
    JevProvider,
    TypedDecisionClient,
    TypedDecisionUnavailable,
    choice,
    get_provider,
    noul,
    score,
)
from typed_decision.privacy import enforce_privacy_gate, set_custom_gate_hook
from typed_decision.providers.jev import (
    DEFAULT_ENDPOINT,
    JEV_MODEL,
    NoAuthRedirectHandler,
    _require_https,
)


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


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests run with clean typed-decision environment by default."""
    monkeypatch.delenv("MAGPIE_TYPED_DECISION_PROVIDER", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.delenv("MAGPIE_PRIVACY_GATE_STRICT", raising=False)
    set_custom_gate_hook(None)


# ---------------------------------------------------------------------------
# 1. Construction and Missing Key Tests
# ---------------------------------------------------------------------------


def test_missing_key_at_construction_raises_unavailable() -> None:
    """Missing API key must raise TypedDecisionUnavailable at provider construction."""
    with pytest.raises(TypedDecisionUnavailable, match="Missing API key"):
        JevProvider()


def test_explicit_key_at_construction_succeeds() -> None:
    """Providing explicit api_key succeeds at construction."""
    provider = JevProvider(api_key="explicit-secret-key")
    assert provider.name == "jev"
    assert provider.model == JEV_MODEL


def test_env_var_key_at_construction_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting TYPESAFE_API_KEY environment variable succeeds at construction."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "env-secret-key")
    provider = JevProvider()
    assert provider.name == "jev"


def test_fallback_env_var_key_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting JEV_API_KEY environment variable succeeds as fallback."""
    monkeypatch.setenv("JEV_API_KEY", "jev-fallback-key")
    provider = JevProvider()
    assert provider.name == "jev"


# ---------------------------------------------------------------------------
# 2. Pinned Model Version (RFC-AI-0004 § Principle 3)
# ---------------------------------------------------------------------------


def test_model_version_is_pinned_constant() -> None:
    """Model version must be a pinned constant and never 'latest'."""
    assert JEV_MODEL == "systemone-2026-06-01"
    assert "latest" not in JEV_MODEL.lower()

    provider = JevProvider(api_key="test-key")
    assert provider.model == JEV_MODEL
    assert "latest" not in provider.model.lower()


# ---------------------------------------------------------------------------
# 3. Successful Operation Calls (Mocked)
# ---------------------------------------------------------------------------


def test_jev_choice_success() -> None:
    """Mocked successful choice operation returns {label, confidence}."""
    provider = JevProvider(api_key="test-key")
    expected_response = {
        "label": "bug",
        "confidence": 0.96,
    }

    mock_resp = _make_mock_response(expected_response)

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        result = provider.choice("Classify issue description", ["bug", "feature", "question"])

        assert result == {"label": "bug", "confidence": 0.96}
        assert mock_open.call_count == 1

        req: urllib.request.Request = mock_open.call_args[0][0]
        assert req.full_url == DEFAULT_ENDPOINT
        assert req.headers["Authorization"] == "Bearer test-key"
        assert req.headers["Content-type"] == "application/json"

        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        assert body["model"] == JEV_MODEL
        assert body["operation"] == "choice"
        assert body["prompt"] == "Classify issue description"
        assert body["options"] == ["bug", "feature", "question"]


def test_jev_score_success() -> None:
    """Mocked successful score operation returns {value, confidence}."""
    provider = JevProvider(api_key="test-key")
    expected_response = {
        "value": 4.5,
        "confidence": 0.89,
    }

    mock_resp = _make_mock_response(expected_response)

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        result = provider.score("Rate severity of vulnerability", scale=(1, 5))

        assert result == {"value": 4.5, "confidence": 0.89}
        assert mock_open.call_count == 1

        req: urllib.request.Request = mock_open.call_args[0][0]
        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        assert body["operation"] == "score"
        assert body["scale"] == [1, 5]


def test_jev_noul_success() -> None:
    """Mocked successful noul operation returns {probability}."""
    provider = JevProvider(api_key="test-key")
    expected_response = {
        "probability": 0.78,
    }

    mock_resp = _make_mock_response(expected_response)

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        result = provider.noul("Is this report actionable?")

        assert result == {"probability": 0.78}
        assert mock_open.call_count == 1

        req: urllib.request.Request = mock_open.call_args[0][0]
        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        assert body["operation"] == "noul"
        assert body["prompt"] == "Is this report actionable?"


def test_jev_nested_result_object() -> None:
    """Provider handles nested 'result' or 'decision' dictionaries from backend."""
    provider = JevProvider(api_key="test-key")
    nested_response = {
        "result": {
            "label": "feature",
            "confidence": 0.92,
        }
    }
    mock_resp = _make_mock_response(nested_response)

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        res = provider.choice("Request new CLI flag", ["bug", "feature"])
        assert res == {"label": "feature", "confidence": 0.92}


# ---------------------------------------------------------------------------
# 4. Timeout and Retry Policy Tests
# ---------------------------------------------------------------------------


def test_timeout_retries_once_then_unavailable() -> None:
    """On timeout, client retries exactly once with backoff, then raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key", backoff_seconds=0.001)

    timeout_exc = TimeoutError("Connection timed out")

    with patch("urllib.request.OpenerDirector.open", side_effect=timeout_exc) as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="timed out after retry"):
            provider.choice("Prompt", ["opt1", "opt2"])

        # Must have attempted exactly 2 times (initial attempt + 1 retry)
        assert mock_open.call_count == 2


def test_timeout_on_urlerror_retries_once_then_unavailable() -> None:
    """URLError caused by timeout retries once, then raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key", backoff_seconds=0.001)
    timeout_url_err = urllib.error.URLError("timed out")

    with patch("urllib.request.OpenerDirector.open", side_effect=timeout_url_err) as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="timed out after retry"):
            provider.score("Prompt", (1, 10))

        assert mock_open.call_count == 2


def test_timeout_first_attempt_retry_succeeds() -> None:
    """First attempt times out, retry succeeds: operation returns response."""
    provider = JevProvider(api_key="test-key", backoff_seconds=0.001)

    mock_success = _make_mock_response({"probability": 0.65})
    side_effects = [TimeoutError("Transient timeout"), mock_success]

    with patch("urllib.request.OpenerDirector.open", side_effect=side_effects) as mock_open:
        res = provider.noul("Test prompt")
        assert res == {"probability": 0.65}
        assert mock_open.call_count == 2


# ---------------------------------------------------------------------------
# 5. Outbound Content Passes Through Privacy-LLM Gate
# ---------------------------------------------------------------------------


def test_outbound_passes_through_privacy_gate() -> None:
    """Every outbound prompt must be routed through enforce_privacy_gate before dispatch."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"label": "approved", "confidence": 1.0})

    with (
        patch("typed_decision.providers.jev.enforce_privacy_gate", wraps=enforce_privacy_gate) as mock_gate,
        patch("urllib.request.OpenerDirector.open", return_value=mock_resp),
    ):
        provider.choice("Confidential triage prompt", ["approved", "rejected"])

        mock_gate.assert_called_once_with("Confidential triage prompt", DEFAULT_ENDPOINT)


def test_privacy_gate_redaction_is_propagated_outbound() -> None:
    """If the privacy gate sanitizes or redacts the prompt, the sanitized text is sent."""
    provider = JevProvider(api_key="test-key")

    def custom_redactor(prompt: str, endpoint: str) -> str:
        return prompt.replace("secret_identifier", "[REDACTED]")

    set_custom_gate_hook(custom_redactor)
    mock_resp = _make_mock_response({"probability": 0.99})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        provider.noul("Analyzing report for secret_identifier vulnerability")

        req: urllib.request.Request = mock_open.call_args[0][0]
        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        # Verify the payload carried the gate's vetted text, not the raw secret
        assert body["prompt"] == "Analyzing report for [REDACTED] vulnerability"
        assert "secret_identifier" not in body["prompt"]


def test_privacy_gate_rejection_prevents_network_egress() -> None:
    """When the privacy gate rejects an endpoint, no HTTP network call is made."""
    provider = JevProvider(api_key="test-key")

    def rejecting_gate(prompt: str, endpoint: str) -> str:
        raise TypedDecisionUnavailable(f"Privacy-LLM gate blocked outbound egress to {endpoint}")

    set_custom_gate_hook(rejecting_gate)

    with patch("urllib.request.OpenerDirector.open") as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="Privacy-LLM gate blocked"):
            provider.choice("Test prompt", ["a", "b"])

        # No network call was attempted
        assert mock_open.call_count == 0


def test_privacy_gate_strict_mode_without_config_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strict privacy mode rejects third-party endpoint when privacy-llm.md is missing."""
    monkeypatch.setenv("MAGPIE_PRIVACY_GATE_STRICT", "true")
    provider = JevProvider(api_key="test-key")

    with pytest.raises(TypedDecisionUnavailable, match="Privacy-LLM gate rejected"):
        provider.choice("Test prompt", ["a", "b"])


def test_privacy_gate_opt_in_config(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Privacy gate approves third-party endpoint when declared in privacy-llm.md opt-in."""
    config_file = tmp_path / "privacy-llm.md"
    config_file.write_text(
        "# Privacy LLM Configuration\n\n"
        "## Approved third-party endpoints (opt-in)\n\n"
        "- api.typesafe.ai (TypeSafe Jev)\n"
        "  - Data-residency contract: https://typesafe.ai/legal/dpa-strict\n"
        "  - Approved-by: Security Team 2026-09-01\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(config_file))
    monkeypatch.setenv("MAGPIE_PRIVACY_GATE_STRICT", "true")

    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"probability": 0.5})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        res = provider.noul("Test prompt")
        assert res == {"probability": 0.5}


# ---------------------------------------------------------------------------
# 6. Provider Registry and Configuration Resolution
# ---------------------------------------------------------------------------


def test_registry_explicit_env_jev(monkeypatch: pytest.MonkeyPatch) -> None:
    """MAGPIE_TYPED_DECISION_PROVIDER=jev resolves to JevProvider."""
    monkeypatch.setenv("MAGPIE_TYPED_DECISION_PROVIDER", "jev")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    provider = get_provider()
    assert isinstance(provider, JevProvider)
    assert provider.name == "jev"


def test_registry_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """MAGPIE_TYPED_DECISION_PROVIDER=unknown raises TypedDecisionUnavailable."""
    monkeypatch.setenv("MAGPIE_TYPED_DECISION_PROVIDER", "unsupported_provider")

    with pytest.raises(TypedDecisionUnavailable, match="Unknown typed decision provider"):
        get_provider()


def test_registry_unset_defaults_to_jev_if_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """When MAGPIE_TYPED_DECISION_PROVIDER is unset, defaults to jev if credentials exist."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    provider = get_provider()
    assert isinstance(provider, JevProvider)


def test_registry_unset_unavailable_if_unconfigured() -> None:
    """When MAGPIE_TYPED_DECISION_PROVIDER is unset and no credentials, reports unavailable."""
    with pytest.raises(TypedDecisionUnavailable, match="No typed decision provider configured"):
        get_provider()


# ---------------------------------------------------------------------------
# 7. Fail-Open on Network and Provider Errors
# ---------------------------------------------------------------------------


def test_http_error_fail_open() -> None:
    """HTTP 500 error raises TypedDecisionUnavailable without fabricated fallback."""
    provider = JevProvider(api_key="test-key")
    err_body = json.dumps({"error": "Internal server error in model execution"}).encode("utf-8")
    http_err = urllib.error.HTTPError(
        url=DEFAULT_ENDPOINT,
        code=500,
        msg="Internal Server Error",
        hdrs=MagicMock(),
        fp=io.BytesIO(err_body),
    )

    with patch("urllib.request.OpenerDirector.open", side_effect=http_err):
        with pytest.raises(TypedDecisionUnavailable, match="HTTP 500"):
            provider.choice("Test", ["a", "b"])


def test_http_auth_error_fail_open() -> None:
    """HTTP 401 Unauthorized raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="bad-key")
    http_err = urllib.error.HTTPError(
        url=DEFAULT_ENDPOINT,
        code=401,
        msg="Unauthorized",
        hdrs=MagicMock(),
        fp=io.BytesIO(b'{"error": "Invalid API key"}'),
    )

    with patch("urllib.request.OpenerDirector.open", side_effect=http_err):
        with pytest.raises(TypedDecisionUnavailable, match="HTTP 401"):
            provider.score("Test", (1, 5))


def test_invalid_json_fail_open() -> None:
    """Non-JSON response raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response("Bad Gateway (HTML error page)", status=502)

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="Failed to parse JSON"):
            provider.noul("Test")


def test_choice_empty_options_raises() -> None:
    """Passing empty options list raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    with pytest.raises(TypedDecisionUnavailable, match="non-empty list of options"):
        provider.choice("Test prompt", [])


def test_choice_missing_label_in_response() -> None:
    """Response missing label raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"unexpected": 123})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="missing 'label'"):
            provider.choice("Test", ["a", "b"])


# ---------------------------------------------------------------------------
# 8. High-Level Convenience Functions and Client API
# ---------------------------------------------------------------------------


def test_functional_and_client_api() -> None:
    """Module-level functions and TypedDecisionClient wrap provider methods."""
    mock_provider = MagicMock(spec=DecisionProvider)
    mock_provider.choice.return_value = {"label": "mock_choice", "confidence": 0.9}
    mock_provider.score.return_value = {"value": 8, "confidence": 0.85}
    mock_provider.noul.return_value = {"probability": 0.42}

    # Functional calls with explicit provider
    assert choice("test", ["a", "b"], provider=mock_provider) == {"label": "mock_choice", "confidence": 0.9}
    assert score("test", (1, 10), provider=mock_provider) == {"value": 8, "confidence": 0.85}
    assert noul("test", provider=mock_provider) == {"probability": 0.42}

    # Client instance
    client = TypedDecisionClient(provider=mock_provider)
    assert client.choice("test", ["a", "b"]) == {"label": "mock_choice", "confidence": 0.9}
    assert client.score("test", (1, 10)) == {"value": 8, "confidence": 0.85}
    assert client.noul("test") == {"probability": 0.42}


# ---------------------------------------------------------------------------
# 9. Security Guards: HTTPS & Redirect Handler
# ---------------------------------------------------------------------------


def test_https_enforced() -> None:
    """Insecure remote HTTP URLs must be rejected."""
    with pytest.raises(TypedDecisionUnavailable, match="must use HTTPS"):
        _require_https("http://api.typesafe.ai/v1/systemone")

    # Localhost allowed for test fixtures
    _require_https("http://127.0.0.1:8080/v1/systemone")
    _require_https("https://api.typesafe.ai/v1/systemone")


def test_no_auth_redirect_handler_blocks_redirects() -> None:
    """Redirect handler must reject redirects to prevent leaking Bearer tokens."""
    handler = NoAuthRedirectHandler()
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone")

    with pytest.raises(TypedDecisionUnavailable, match="refusing to forward credentials"):
        handler.redirect_request(req, None, 302, "Found", {}, "https://attacker.example.com")
