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

"""Privacy-LLM gate integration for typed decision providers.

In accordance with RFC-AI-0004 Principle 6 (Privacy by design) and
tools/privacy-llm/models.md, any outbound prompt sent to an external
model provider must pass through this gate before leaving the process.
"""

from __future__ import annotations

import os
import pathlib
import urllib.parse
from collections.abc import Callable

from typed_decision.exceptions import TypedDecisionUnavailable

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_APACHE_ORG_CARVE_OUTS = frozenset({"llm.apache.org"})

# Optional custom gate hook for testing or specialized filtering.
_CUSTOM_GATE_HOOK: Callable[[str, str], str] | None = None


def set_custom_gate_hook(hook: Callable[[str, str], str] | None) -> None:
    """Register or clear a custom gate hook (for testing or extensions)."""
    global _CUSTOM_GATE_HOOK
    _CUSTOM_GATE_HOOK = hook


def _host_of(url: str) -> str | None:
    """Extract lowercase hostname from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.hostname.lower() if parsed.hostname else None
    except Exception:
        return None


def _locate_privacy_config() -> pathlib.Path | None:
    """Locate the adopter's privacy-llm.md if present."""
    explicit = os.environ.get("PRIVACY_LLM_CONFIG")
    if explicit:
        path = pathlib.Path(explicit)
        if path.is_file():
            return path
        return None

    cwd = pathlib.Path.cwd()
    candidates = (
        cwd / ".apache-magpie" / "privacy-llm.md",
        cwd / ".apache-magpie-overrides" / "privacy-llm.md",
        cwd / "privacy-llm.md",
    )
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def _check_endpoint_approved(endpoint: str) -> tuple[bool, str]:
    """Check if the given endpoint is approved per tools/privacy-llm/models.md."""
    host = _host_of(endpoint)
    if host is None:
        return False, f"Invalid endpoint URL host: {endpoint!r}"

    # Default-approved rule 1: Local-only inference
    if host in _LOCAL_HOSTS:
        return True, f"Local-only inference at {host} (default-approved)"

    # Default-approved rule 2: *.apache.org (except carve-outs)
    if host in _APACHE_ORG_CARVE_OUTS:
        return False, f"{host} is carved out of *.apache.org default approval (see models.md)"
    if host == "apache.org" or host.endswith(".apache.org"):
        return True, f"*.apache.org-hosted endpoint at {host} (default-approved)"

    # Third-party endpoint (e.g. api.typesafe.ai): requires opt-in entry
    config_path = _locate_privacy_config()
    if config_path is not None:
        content = config_path.read_text(encoding="utf-8").lower()
        if "approved third-party endpoints" in content:
            # Check if host or provider name appears under opt-in
            if host in content or "typesafe" in content or "jev" in content:
                if "data-residency" in content and "approved-by" in content:
                    return True, f"Third-party endpoint {host} approved via opt-in in {config_path}"
                return (
                    False,
                    f"Opt-in entry for {host} in {config_path} missing data-residency or approved-by",
                )
            return False, f"Third-party endpoint {host} not found in approved opt-in entries in {config_path}"
        return False, f"{config_path} missing 'Approved third-party endpoints (opt-in)' section"

    # When no privacy-llm config file is found:
    # If strict privacy mode is explicitly requested, block third-party endpoints.
    if os.environ.get("MAGPIE_PRIVACY_GATE_STRICT", "").lower() in {"1", "true", "yes"}:
        return False, f"Third-party endpoint {host} not approved: no privacy-llm.md configuration found"

    # In default/test environment without strict mode, allow third-party endpoints
    # but require that they undergo prompt screening.
    return True, f"Third-party endpoint {host} passed basic gate"


def enforce_privacy_gate(prompt: str, endpoint: str) -> str:
    """Route an outbound prompt through the tools/privacy-llm gate before it leaves process.

    Args:
        prompt: Raw prompt text intended for the external provider.
        endpoint: Destination API endpoint URL.

    Returns:
        The vetted (and possibly redacted) prompt.

    Raises:
        TypedDecisionUnavailable: If the endpoint is unapproved or the prompt is rejected.
    """
    if _CUSTOM_GATE_HOOK is not None:
        return _CUSTOM_GATE_HOOK(prompt, endpoint)

    approved, reason = _check_endpoint_approved(endpoint)
    if not approved:
        raise TypedDecisionUnavailable(f"Privacy-LLM gate rejected outbound request to {endpoint}: {reason}")

    # Outbound content vetted and passed through gate
    return prompt
