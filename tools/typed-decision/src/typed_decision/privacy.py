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

from checker.check import check_endpoint

from typed_decision.exceptions import TypedDecisionUnavailable

DEFAULT_ENDPOINT: str = "https://api.typesafe.ai/v1/systemone"


def _check_endpoint_approved(endpoint: str, provider_name: str | None = None) -> tuple[bool, str]:
    """Check if the given endpoint is approved per tools/privacy-llm/models.md.

    Denies by default per tools/privacy-llm/models.md ('Anything else -> ✗').
    Binds opt-in checks to the specific URL/host. Only applies the provider-name
    label when endpoint matches DEFAULT_ENDPOINT to prevent name-only opt-ins from
    authorizing arbitrary destination hosts.
    """
    raw_desc = f"{provider_name} ({endpoint})" if endpoint == DEFAULT_ENDPOINT and provider_name else endpoint
    verdict = check_endpoint(endpoint, raw_desc=raw_desc)
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
    approved, reason = _check_endpoint_approved(endpoint, provider_name=provider_name)
    if not approved:
        raise TypedDecisionUnavailable(f"Privacy-LLM gate rejected outbound request to {endpoint}: {reason}")

    return prompt
