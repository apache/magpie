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
The gate strictly denies unapproved endpoints by default.
"""

from __future__ import annotations

import pathlib
import sys
from collections.abc import Callable

from typed_decision.exceptions import TypedDecisionUnavailable

try:
    from checker.check import _approve_by_default_rules, _approve_by_opt_in  # type: ignore[import-untyped]
    from checker.config import LLMEntry, locate_config_path, parse_config  # type: ignore[import-untyped]
except ImportError:
    _checker_src = pathlib.Path(__file__).resolve().parents[3] / "privacy-llm" / "checker" / "src"
    if _checker_src.is_dir() and str(_checker_src) not in sys.path:
        sys.path.insert(0, str(_checker_src))
    from checker.check import _approve_by_default_rules, _approve_by_opt_in  # type: ignore[import-untyped]
    from checker.config import LLMEntry, locate_config_path, parse_config  # type: ignore[import-untyped]

# Optional custom gate hook for testing or specialized filtering.
_CUSTOM_GATE_HOOK: Callable[[str, str], str] | None = None


def set_custom_gate_hook(hook: Callable[[str, str], str] | None) -> None:
    """Register or clear a custom gate hook (for testing or extensions)."""
    global _CUSTOM_GATE_HOOK
    _CUSTOM_GATE_HOOK = hook


def _check_endpoint_approved(endpoint: str, provider_name: str | None = None) -> tuple[bool, str]:
    """Check if the given endpoint is approved per tools/privacy-llm/models.md.

    Denies by default per tools/privacy-llm/models.md ('Anything else -> ✗').
    Uses tools/privacy-llm/checker for canonical parsing, comment stripping,
    and placeholder detection.
    """
    raw_desc = f"{provider_name} ({endpoint})" if provider_name else endpoint
    entry = LLMEntry(raw=raw_desc, url=endpoint)

    # 1. Check default approval rules (localhost, *.apache.org except carve-outs, Claude Code)
    verdict = _approve_by_default_rules(entry)
    if verdict is not None:
        return verdict.approved, verdict.reason

    # 2. Third-party endpoint: requires explicit opt-in entry in privacy-llm.md
    try:
        config_path = locate_config_path()
    except FileNotFoundError as err:
        return False, f"Third-party endpoint {endpoint} denied (no privacy-llm config found): {err}"

    try:
        config = parse_config(config_path)
    except Exception as err:
        return False, f"Failed to parse privacy-llm config at {config_path}: {err}"

    verdict = _approve_by_opt_in(entry, config.opt_in)
    return verdict.approved, verdict.reason


def enforce_privacy_gate(prompt: str, endpoint: str, provider_name: str | None = None) -> str:
    """Validate that the outbound prompt is destined for an approved endpoint.

    In accordance with RFC-AI-0004 and tools/privacy-llm/models.md, any outbound
    prompt must never reach an unapproved endpoint. The gate is conservative and
    denies by default: third-party endpoints must be explicitly approved by PMC
    members in `<project-config>/privacy-llm.md` with a non-empty Data-residency
    contract and non-placeholder Approved-by line.

    Per tools/privacy-llm/wiring.md, skills processing private source content must
    redact PII (using `tools/privacy-llm/redactor`) prior to invoking downstream
    tools. This gate strictly guards the network egress boundary.

    Args:
        prompt: Raw or pre-redacted prompt text intended for the external provider.
        endpoint: Destination API endpoint URL.
        provider_name: Optional provider name (e.g. 'TypeSafe Jev') for opt-in matching.

    Returns:
        The validated prompt text.

    Raises:
        TypedDecisionUnavailable: If the destination endpoint is unapproved.
    """
    if _CUSTOM_GATE_HOOK is not None:
        return _CUSTOM_GATE_HOOK(prompt, endpoint)

    approved, reason = _check_endpoint_approved(endpoint, provider_name=provider_name)
    if not approved:
        raise TypedDecisionUnavailable(f"Privacy-LLM gate rejected outbound request to {endpoint}: {reason}")

    return prompt
