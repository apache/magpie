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
import pathlib
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
from typed_decision.privacy import enforce_privacy_gate
from typed_decision.providers.jev import (
    DEFAULT_ENDPOINT,
    JEV_MODEL,
    NoAuthRedirectHandler,
    _require_https,
)
from typed_decision.registry import _is_jev_configured


def _make_mock_response(body: dict[str, Any] | list[Any] | str | int, status: int = 200) -> MagicMock:
    """Helper to produce a mock HTTP response object for urllib."""
    mock_resp = MagicMock()
    mock_resp.status = status
    if isinstance(body, (dict, list, int)):
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


@pytest.fixture
def approved_privacy_config(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Provide a valid privacy-llm.md approving the default Jev endpoint."""
    config_file = tmp_path / "privacy-llm.md"
    config_file.write_text(
        "# Privacy LLM Configuration\n\n"
        "## Approved third-party endpoints (opt-in)\n\n"
        "- api.typesafe.ai (TypeSafe Jev)\n"
        "  - Data-residency contract: https://typesafe.ai/legal/dpa-strict\n"
        "  - Approved-by: JP 2026-09-01\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(config_file))
    return config_file


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


def test_jev_choice_success(approved_privacy_config: pathlib.Path) -> None:
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


def test_jev_score_success(approved_privacy_config: pathlib.Path) -> None:
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


def test_jev_noul_success(approved_privacy_config: pathlib.Path) -> None:
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


def test_jev_nested_result_object(approved_privacy_config: pathlib.Path) -> None:
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


def test_timeout_retries_once_then_unavailable(approved_privacy_config: pathlib.Path) -> None:
    """On timeout, client retries exactly once with backoff, then raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key", backoff_seconds=0.001)

    timeout_exc = TimeoutError("Connection timed out")

    with patch("urllib.request.OpenerDirector.open", side_effect=timeout_exc) as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="timed out after retry"):
            provider.choice("Prompt", ["opt1", "opt2"])

        # Must have attempted exactly 2 times (initial attempt + 1 retry)
        assert mock_open.call_count == 2


def test_timeout_on_urlerror_retries_once_then_unavailable(approved_privacy_config: pathlib.Path) -> None:
    """URLError caused by timeout retries once, then raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key", backoff_seconds=0.001)
    timeout_url_err = urllib.error.URLError("timed out")

    with patch("urllib.request.OpenerDirector.open", side_effect=timeout_url_err) as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="timed out after retry"):
            provider.score("Prompt", (1, 10))

        assert mock_open.call_count == 2


def test_timeout_first_attempt_retry_succeeds(approved_privacy_config: pathlib.Path) -> None:
    """First attempt times out, retry succeeds: operation returns response."""
    provider = JevProvider(api_key="test-key", backoff_seconds=0.001)

    mock_success = _make_mock_response({"probability": 0.65})
    side_effects = [TimeoutError("Transient timeout"), mock_success]

    with patch("urllib.request.OpenerDirector.open", side_effect=side_effects) as mock_open:
        res = provider.noul("Test prompt")
        assert res == {"probability": 0.65}
        assert mock_open.call_count == 2


# ---------------------------------------------------------------------------
# 5. Outbound Content Passes Through Privacy-LLM Gate (Deny-by-Default)
# ---------------------------------------------------------------------------


def test_outbound_passes_through_privacy_gate(approved_privacy_config: pathlib.Path) -> None:
    """Every outbound prompt must be routed through enforce_privacy_gate before dispatch."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"label": "approved", "confidence": 1.0})

    with (
        patch("typed_decision.providers.jev.enforce_privacy_gate", wraps=enforce_privacy_gate) as mock_gate,
        patch("urllib.request.OpenerDirector.open", return_value=mock_resp),
    ):
        provider.choice("Confidential triage prompt", ["approved", "rejected"])

        mock_gate.assert_called_once_with(
            "Confidential triage prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev"
        )


def test_name_only_opt_in_does_not_approve_different_host(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An opt-in matching 'TypeSafe Jev' by name must not approve an arbitrary endpoint host."""
    config_file = tmp_path / "privacy-llm.md"
    config_file.write_text(
        "# Privacy LLM Configuration\n\n"
        "## Approved third-party endpoints (opt-in)\n\n"
        "- TypeSafe Jev\n"
        "  - Data-residency contract: https://typesafe.ai/legal/dpa\n"
        "  - Approved-by: JP 2026-09-01\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(config_file))

    # DEFAULT_ENDPOINT matches via provider_name
    enforce_privacy_gate("Test prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")

    # Different endpoint must NOT be approved even if provider_name is passed
    with pytest.raises(TypedDecisionUnavailable, match="Privacy-LLM gate rejected outbound request"):
        enforce_privacy_gate(
            "Test prompt",
            "https://unapproved.attacker.example.com/v1",
            provider_name="TypeSafe Jev",
        )


def test_privacy_gate_rejection_prevents_network_egress() -> None:
    """When the privacy gate rejects an endpoint, no HTTP network call is made."""
    provider = JevProvider(api_key="test-key")

    with patch("urllib.request.OpenerDirector.open") as mock_open:
        with pytest.raises(TypedDecisionUnavailable, match="Privacy-LLM gate rejected outbound request"):
            provider.choice("Test prompt", ["a", "b"])

        assert mock_open.call_count == 0


def test_privacy_gate_denies_by_default_when_no_config() -> None:
    """Third-party endpoints are denied by default when no privacy-llm config is found."""
    provider = JevProvider(api_key="test-key")

    with pytest.raises(TypedDecisionUnavailable, match="Privacy-LLM gate rejected outbound request"):
        provider.choice("Test prompt", ["a", "b"])

    with pytest.raises(TypedDecisionUnavailable, match="no privacy-llm config found"):
        enforce_privacy_gate("Test prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")


def test_privacy_gate_denies_missing_config_file(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When PRIVACY_LLM_CONFIG points to a missing file, third-party endpoints are denied."""
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(tmp_path / "nonexistent-privacy-llm.md"))

    with pytest.raises(TypedDecisionUnavailable, match="Failed to parse privacy-llm config"):
        enforce_privacy_gate("Prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")


def test_privacy_gate_denies_unapproved_third_party_endpoint(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Third-party endpoint not listed in opt-in section is denied."""
    config_file = tmp_path / "privacy-llm.md"
    config_file.write_text(
        "# Privacy LLM Configuration\n\n"
        "## Approved third-party endpoints (opt-in)\n\n"
        "- api.other.ai (Other AI Service)\n"
        "  - Data-residency contract: https://other.ai/legal/dpa\n"
        "  - Approved-by: JP 2026-09-01\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(config_file))

    with pytest.raises(TypedDecisionUnavailable, match="no opt-in entry was declared"):
        enforce_privacy_gate("Prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")


def test_privacy_gate_denies_endpoint_in_currently_configured_stack_only(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Endpoint declared only under 'Currently configured LLM stack' is denied without opt-in sign-off."""
    config_file = tmp_path / "privacy-llm.md"
    config_file.write_text(
        "# Privacy LLM Configuration\n\n"
        "## Currently configured LLM stack\n\n"
        "- api.typesafe.ai (TypeSafe Jev)\n\n"
        "## Approved third-party endpoints (opt-in)\n\n"
        "- none\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(config_file))

    with pytest.raises(TypedDecisionUnavailable, match="no opt-in entry was declared"):
        enforce_privacy_gate("Prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")


def test_privacy_gate_denies_placeholder_approved_by(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opt-in entry with placeholder Approved-by (e.g. <pmc-member-initials>) is denied."""
    config_file = tmp_path / "privacy-llm.md"
    config_file.write_text(
        "# Privacy LLM Configuration\n\n"
        "## Approved third-party endpoints (opt-in)\n\n"
        "- api.typesafe.ai (TypeSafe Jev)\n"
        "  - Data-residency contract: https://typesafe.ai/legal/dpa-strict\n"
        "  - Approved-by: <pmc-member-initials> 2026-09-01\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(config_file))

    with pytest.raises(TypedDecisionUnavailable, match="placeholder text"):
        enforce_privacy_gate("Prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")


def test_privacy_gate_denies_missing_data_residency(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opt-in entry missing Data-residency contract is denied."""
    config_file = tmp_path / "privacy-llm.md"
    config_file.write_text(
        "# Privacy LLM Configuration\n\n"
        "## Approved third-party endpoints (opt-in)\n\n"
        "- api.typesafe.ai (TypeSafe Jev)\n"
        "  - Approved-by: JP 2026-09-01\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(config_file))

    with pytest.raises(TypedDecisionUnavailable, match="missing the 'Data-residency contract'"):
        enforce_privacy_gate("Prompt", DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")


def test_privacy_gate_approves_valid_opt_in(approved_privacy_config: pathlib.Path) -> None:
    """Opt-in entry with contract and real PMC Approved-by succeeds."""
    prompt = "Prompt destined for approved provider"
    result = enforce_privacy_gate(prompt, DEFAULT_ENDPOINT, provider_name="TypeSafe Jev")
    assert result == prompt


def test_privacy_gate_approves_default_rules() -> None:
    """Localhost, 127.0.0.1, and *.apache.org endpoints are approved without config."""
    assert enforce_privacy_gate("Test", "http://localhost:8080/v1") == "Test"
    assert enforce_privacy_gate("Test", "http://127.0.0.1:9000/v1") == "Test"
    assert enforce_privacy_gate("Test", "https://infra.apache.org/v1") == "Test"


def test_privacy_gate_denies_carved_out_apache_host() -> None:
    """llm.apache.org is carved out and denied by default without explicit opt-in."""
    with pytest.raises(TypedDecisionUnavailable, match=r"carved out of the \*.apache.org default approval"):
        enforce_privacy_gate("Test", "https://llm.apache.org/v1")


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


def test_registry_is_jev_configured_deduplicated(monkeypatch: pytest.MonkeyPatch) -> None:
    """_is_jev_configured() delegates to _resolve_api_key()."""
    assert _is_jev_configured() is False

    monkeypatch.setenv("TYPESAFE_API_KEY", "key-1")
    assert _is_jev_configured() is True

    monkeypatch.delenv("TYPESAFE_API_KEY")
    monkeypatch.setenv("JEV_API_KEY", "key-2")
    assert _is_jev_configured() is True


# ---------------------------------------------------------------------------
# 7. Fail-Open, Validation, and Error Handling Tests
# ---------------------------------------------------------------------------


def test_http_error_fail_open(approved_privacy_config: pathlib.Path) -> None:
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


def test_http_auth_error_fail_open(approved_privacy_config: pathlib.Path) -> None:
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


def test_invalid_json_fail_open(approved_privacy_config: pathlib.Path) -> None:
    """Non-JSON response raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response("Bad Gateway (HTML error page)", status=502)

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="Failed to parse JSON"):
            provider.noul("Test")


def test_malformed_response_object_handled_fail_open(approved_privacy_config: pathlib.Path) -> None:
    """Non-dictionary JSON responses raise TypedDecisionUnavailable fail-open."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response(["not", "a", "dict"])

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="Malformed response from Jev API"):
            provider.choice("Test", ["a", "b"])


def test_choice_empty_options_raises() -> None:
    """Passing empty options list raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    with pytest.raises(TypedDecisionUnavailable, match="non-empty list of options"):
        provider.choice("Test prompt", [])


def test_choice_missing_label_in_response(approved_privacy_config: pathlib.Path) -> None:
    """Response missing label raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"confidence": 0.95})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="missing 'label'"):
            provider.choice("Test", ["a", "b"])


def test_choice_rejects_missing_confidence(approved_privacy_config: pathlib.Path) -> None:
    """Choice response missing confidence must raise TypedDecisionUnavailable (never default to 1.0)."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"label": "a"})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="missing 'confidence'"):
            provider.choice("Test", ["a", "b"])


def test_choice_rejects_label_not_in_options(approved_privacy_config: pathlib.Path) -> None:
    """Choice response returning a label outside the provided options must raise TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"label": "unexpected", "confidence": 0.9})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="not in candidate options"):
            provider.choice("Test", ["a", "b"])


def test_choice_rejects_invalid_confidence_range(approved_privacy_config: pathlib.Path) -> None:
    """Confidence outside [0.0, 1.0] must raise TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")

    mock_resp_high = _make_mock_response({"label": "a", "confidence": 1.5})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp_high):
        with pytest.raises(TypedDecisionUnavailable, match="outside valid range"):
            provider.choice("Test", ["a", "b"])

    mock_resp_low = _make_mock_response({"label": "a", "confidence": -0.1})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp_low):
        with pytest.raises(TypedDecisionUnavailable, match="outside valid range"):
            provider.choice("Test", ["a", "b"])


def test_choice_rejects_non_numeric_confidence(approved_privacy_config: pathlib.Path) -> None:
    """Non-numeric confidence raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"label": "a", "confidence": "high"})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="non-numeric confidence"):
            provider.choice("Test", ["a", "b"])


def test_score_invalid_scale_argument() -> None:
    """Passing invalid scale (min >= max) raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    with pytest.raises(TypedDecisionUnavailable, match="Invalid scale"):
        provider.score("Test", scale=(5, 1))


def test_score_scalar_scale_normalized(approved_privacy_config: pathlib.Path) -> None:
    """Scalar scale=10 is normalized to (0, 10) and bounds-checked."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"value": 7.5, "confidence": 0.85})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp) as mock_open:
        res = provider.score("Test", scale=10)
        assert res["value"] == 7.5
        assert res["confidence"] == 0.85

        req: urllib.request.Request = mock_open.call_args[0][0]
        assert isinstance(req.data, bytes)
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["scale"] == [0.0, 10.0]


def test_score_scalar_scale_rejects_out_of_bounds(approved_privacy_config: pathlib.Path) -> None:
    """Scalar scale=10 rejects value=42 outside [0, 10]."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"value": 42.0, "confidence": 0.9})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="outside scale range"):
            provider.score("Test", scale=10)


def test_score_rejects_invalid_scalar_scales() -> None:
    """Scalar scale <= 0 or bool is rejected on input."""
    provider = JevProvider(api_key="test-key")
    with pytest.raises(TypedDecisionUnavailable, match="Invalid scale: bool"):
        provider.score("Test", scale=True)

    with pytest.raises(TypedDecisionUnavailable, match="strictly positive"):
        provider.score("Test", scale=0)

    with pytest.raises(TypedDecisionUnavailable, match="strictly positive"):
        provider.score("Test", scale=-5)


def test_score_rejects_missing_value(approved_privacy_config: pathlib.Path) -> None:
    """Score response missing value raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"confidence": 0.8})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="missing 'value'"):
            provider.score("Test", scale=(1, 5))


def test_score_rejects_value_outside_scale(approved_privacy_config: pathlib.Path) -> None:
    """Score response value outside scale raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")

    mock_resp_high = _make_mock_response({"value": 6.0, "confidence": 0.9})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp_high):
        with pytest.raises(TypedDecisionUnavailable, match="outside scale"):
            provider.score("Test", scale=(1, 5))

    mock_resp_low = _make_mock_response({"value": 0.5, "confidence": 0.9})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp_low):
        with pytest.raises(TypedDecisionUnavailable, match="outside scale"):
            provider.score("Test", scale=(1, 5))


def test_score_rejects_missing_confidence(approved_privacy_config: pathlib.Path) -> None:
    """Score response missing confidence raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"value": 3.0})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="missing 'confidence'"):
            provider.score("Test", scale=(1, 5))


def test_score_rejects_invalid_confidence_range(approved_privacy_config: pathlib.Path) -> None:
    """Score response confidence outside [0.0, 1.0] raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"value": 3.0, "confidence": 1.2})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="outside valid range"):
            provider.score("Test", scale=(1, 5))


def test_noul_rejects_missing_probability(approved_privacy_config: pathlib.Path) -> None:
    """Noul response missing probability raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"decision": "yes"})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="missing 'probability'"):
            provider.noul("Test")


def test_noul_rejects_invalid_probability_range(approved_privacy_config: pathlib.Path) -> None:
    """Probability outside [0.0, 1.0] raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")

    mock_resp_high = _make_mock_response({"probability": 1.1})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp_high):
        with pytest.raises(TypedDecisionUnavailable, match="outside valid range"):
            provider.noul("Test")

    mock_resp_low = _make_mock_response({"probability": -0.2})
    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp_low):
        with pytest.raises(TypedDecisionUnavailable, match="outside valid range"):
            provider.noul("Test")


def test_noul_rejects_non_numeric_probability(approved_privacy_config: pathlib.Path) -> None:
    """Non-numeric probability raises TypedDecisionUnavailable."""
    provider = JevProvider(api_key="test-key")
    mock_resp = _make_mock_response({"probability": "likely"})

    with patch("urllib.request.OpenerDirector.open", return_value=mock_resp):
        with pytest.raises(TypedDecisionUnavailable, match="non-numeric probability"):
            provider.noul("Test")


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
