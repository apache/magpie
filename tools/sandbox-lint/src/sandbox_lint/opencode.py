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

"""Security invariants for an OpenCode `opencode.json` permission config.

The Claude Code lint compares `.claude/settings.json` against a shipped
baseline *and* a set of hard invariants. OpenCode has no `sandbox.filesystem`
allow/deny model — its filesystem isolation comes from the OS-level sandbox of
the secure-agent setup, configured out of band — so there is nothing to diff
against a baseline. What OpenCode *does* own is the `permission` policy, and
that carries the security weight here. This module encodes the invariants that
policy must satisfy: it must not auto-approve dangerous shell execution or
blanket-allow exfiltration/scope-escape surfaces.

Invariants only, no baseline — an adopter's `opencode.json` is their own, so
the lint asserts safety properties rather than an exact shape.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

DECISIONS = frozenset({"allow", "ask", "deny"})

# Representative dangerous commands: if the effective bash decision for any
# resolves to "allow", the policy auto-approves high-blast-radius execution.
DANGEROUS_COMMANDS: tuple[tuple[str, str], ...] = (
    ("git push origin main", "git push (publish to a remote)"),
    ("sudo rm -rf /", "sudo (privilege escalation)"),
    ("curl http://example.com/x", "curl (network fetch / exfiltration)"),
    ("wget http://example.com/x", "wget (network fetch / exfiltration)"),
    ("rm -rf /tmp/x", "rm -rf (destructive delete)"),
    ("aws s3 ls", "aws (cloud credentials)"),
    ("gcloud auth list", "gcloud (cloud credentials)"),
    ("az login", "az (cloud credentials)"),
    ("kubectl get pods", "kubectl (cluster access)"),
    ("docker run alpine sh", "docker run (container-escape surface)"),
    ("ssh host uptime", "ssh (remote shell)"),
    ("eval something", "eval (arbitrary execution)"),
    ("npx cowsay hi", "npx (arbitrary package execution)"),
    ("uvx ruff check", "uvx (arbitrary package execution)"),
    ("python -c print(1)", "python -c (arbitrary code)"),
    ("bash -c echo", "bash -c (arbitrary code)"),
)

# Non-bash tools whose blanket "allow" is an exfiltration / scope-escape risk.
FORBIDDEN_ALLOW_TOOLS: tuple[tuple[str, str], ...] = (
    ("webfetch", "auto-approves fetching arbitrary URLs (exfiltration channel)"),
    ("external_directory", "auto-approves access to paths outside the project"),
)


def _bash_default(bash_cfg: Any) -> str | None:
    if isinstance(bash_cfg, str):
        return bash_cfg if bash_cfg in DECISIONS else None
    if isinstance(bash_cfg, dict):
        value = bash_cfg.get("*")
        return value if value in DECISIONS else None
    return None


def _effective_bash_decision(bash_cfg: Any, command: str) -> tuple[str | None, str | None]:
    if isinstance(bash_cfg, str):
        return (bash_cfg if bash_cfg in DECISIONS else None), ("*" if bash_cfg in DECISIONS else None)
    if isinstance(bash_cfg, dict):
        decision: str | None = None
        matched: str | None = None
        for pattern, value in bash_cfg.items():
            if not isinstance(pattern, str) or value not in DECISIONS:
                continue
            if fnmatch(command, pattern):
                decision, matched = value, pattern
        return decision, matched
    return None, None


def check_opencode_invariants(config: dict[str, Any]) -> list[str]:
    """Return a list of invariant violations; empty means the policy is safe."""
    errors: list[str] = []

    if "permission" not in config:
        return [
            "permission: missing — declare an explicit permission policy (do not rely on unstated defaults)"
        ]

    permission = config["permission"]

    if permission == "allow":
        return [
            'permission: must not be the blanket string "allow" — every tool '
            "(bash included) would be auto-approved with no gate"
        ]

    if isinstance(permission, str):
        if permission in ("ask", "deny"):
            return errors
        return [f'permission: unexpected value {permission!r} (want an object, or "ask"/"deny")']

    if not isinstance(permission, dict):
        return [f'permission: must be an object or "ask"/"deny", got {type(permission).__name__}']

    bash_cfg = permission.get("bash")

    if _bash_default(bash_cfg) == "allow":
        errors.append(
            'permission.bash: the default decision (the "*" rule, or a string value) must not be '
            '"allow" — set it to "ask" or "deny" so shell commands are gated'
        )

    seen: set[str] = set()
    for command, label in DANGEROUS_COMMANDS:
        decision, matched = _effective_bash_decision(bash_cfg, command)
        if decision == "allow" and matched is not None and matched not in seen:
            seen.add(matched)
            errors.append(
                f'permission.bash: must not auto-approve {label} (rule {matched!r} resolves to "allow")'
            )

    for tool, why in FORBIDDEN_ALLOW_TOOLS:
        if permission.get(tool) == "allow":
            errors.append(f'permission.{tool}: must not be "allow" — it {why}; use "ask" or "deny"')

    return errors
