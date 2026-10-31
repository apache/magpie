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

"""Audit an OpenCode `permission` config for over-permissioning.

OpenCode's permission model differs in shape from Claude Code's flat
`permissions.allow[]` list, so the audit is a separate classifier — but the
*intent* is the same one this tool applies to Claude: flag configuration that
**auto-approves dangerous shell execution** (the OpenCode analog of the broad
`FORBIDDEN_PATTERNS` wildcards the Claude audit removes).

The `permission` value in `opencode.json` is either:

- a string (`"allow"` / `"ask"` / `"deny"`) applied to every tool, or
- an object keyed by tool (`bash`, `edit`, `webfetch`, …). The `bash` key may
  itself be an object mapping glob command patterns to a decision, evaluated
  **last-matching-rule-wins** with a `"*"` default
  (per <https://opencode.ai/docs/permissions/>).

Pure data + classification — no I/O. The CLI layer reads the file and renders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

DECISIONS = frozenset({"allow", "ask", "deny"})

# Canonical dangerous commands. If a config's *effective* bash decision for any
# of these resolves to "allow", it auto-approves arbitrary or high-blast-radius
# execution. Kept representative (not exhaustive), the same posture as the
# Claude `FORBIDDEN_PATTERNS` list.
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


@dataclass(frozen=True)
class OpenCodeFinding:
    """A single OpenCode permission finding.

    `kind` is one of ``blanket-allow`` (the whole `permission` is "allow"),
    ``bash-allow-all`` (bash defaults to allow), or ``dangerous-allow`` (a
    specific rule auto-approves a dangerous command family).
    """

    severity: str  # always "forbidden" today
    kind: str
    detail: str
    json_pointer: str


@dataclass
class OpenCodeAuditResult:
    forbidden: list[OpenCodeFinding] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.forbidden)


def bash_default(bash_cfg: object) -> str | None:
    """The decision applied to a bash command that matches no specific rule.

    A string `bash` value is itself the default; an object's default is its
    `"*"` entry (OpenCode's own built-in default when absent is "ask").
    """
    if isinstance(bash_cfg, str):
        return bash_cfg if bash_cfg in DECISIONS else None
    if isinstance(bash_cfg, dict):
        value = bash_cfg.get("*")
        return value if value in DECISIONS else None
    return None


def effective_bash_decision(bash_cfg: object, command: str) -> tuple[str | None, str | None]:
    """Return ``(decision, matched_pattern)`` for `command`, last-match-wins."""
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


def audit_opencode(config: dict) -> OpenCodeAuditResult:
    """Classify an ``opencode.json`` dict for dangerous auto-approval."""
    result = OpenCodeAuditResult()
    permission = config.get("permission")

    # 1. The whole permission policy is a blanket "allow".
    if permission == "allow":
        result.forbidden.append(
            OpenCodeFinding(
                "forbidden",
                "blanket-allow",
                '`permission` is "allow" — every tool (bash included) is auto-approved with no gate. '
                'Use an object policy that gates bash (e.g. {"bash": {"*": "ask"}}).',
                ".permission",
            )
        )
        return result

    if not isinstance(permission, dict):
        # Absent, or the safe "ask"/"deny" strings — nothing to flag.
        return result

    bash_cfg = permission.get("bash")
    default = bash_default(bash_cfg)

    # 2. bash defaults to allow (string "allow", or "*": "allow").
    if default == "allow":
        result.forbidden.append(
            OpenCodeFinding(
                "forbidden",
                "bash-allow-all",
                'the default `permission.bash` decision is "allow" — every shell command is '
                'auto-approved. Set the default ("*") to "ask" or "deny".',
                ".permission.bash",
            )
        )

    # 3. Specific rules that auto-approve a dangerous family while the default
    #    is stricter (when the default already allows all, #2 covers it).
    if default != "allow":
        seen: set[str] = set()
        for command, label in DANGEROUS_COMMANDS:
            decision, matched = effective_bash_decision(bash_cfg, command)
            if decision == "allow" and matched is not None and matched != "*" and matched not in seen:
                seen.add(matched)  # one finding per over-broad rule, not per sample command
                result.forbidden.append(
                    OpenCodeFinding(
                        "forbidden",
                        "dangerous-allow",
                        f'{label} is auto-approved by rule {matched!r} = "allow".',
                        f'.permission.bash["{matched}"]',
                    )
                )

    return result
