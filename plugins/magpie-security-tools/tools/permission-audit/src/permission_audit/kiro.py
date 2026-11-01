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

"""Audit a Kiro CLI agent-config for shell over-permissioning.

Same intent as the Claude and OpenCode audits — flag config that
**auto-approves dangerous shell execution** — over Kiro's allowlist/denylist
model (`allowedTools` + `toolsSettings.shell`) rather than OpenCode's
per-command `permission.bash` decision map.

Kiro resolution (<https://kiro.dev/docs/cli/reference/built-in-tools>):
the shell tool (`shell`/`execute_bash`/`execute_cmd`), `*`, or `@builtin` in
`allowedTools` auto-approves *every* shell command (overriding
`toolsSettings`); otherwise `deniedCommands` (regex, evaluated first) → deny,
`allowedCommands` (regex) → allow, `denyByDefault` → deny, else prompt.
`allowedCommands`/`deniedCommands` are `\\A..\\z`-anchored regex, matched here
with :func:`re.fullmatch`.

Pure data + classification — no I/O. The CLI layer reads the file and renders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from permission_audit.opencode import DANGEROUS_COMMANDS

SHELL_TOOL_NAMES = frozenset({"shell", "execute_bash", "execute_cmd"})
WILDCARD_TOOL_NAMES = frozenset({"*", "@builtin"})
EXFIL_TOOLS: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"web_fetch", "webfetch"}), "auto-approves fetching arbitrary URLs (exfiltration)"),
    (frozenset({"aws", "use_aws"}), "auto-approves AWS CLI calls (cloud credentials)"),
)
_BLANKET_TRUSTED = frozenset({".*", ".+", "^.*$", "(.*)"})


@dataclass(frozen=True)
class KiroFinding:
    """A single Kiro permission finding.

    `kind` is one of ``shell-allow-all`` (the shell tool is auto-approved via
    `allowedTools`), ``dangerous-allow`` (an `allowedCommands` rule
    auto-approves a dangerous family), or ``exfil-allow`` (a
    credential/exfiltration surface is auto-approved).
    """

    severity: str  # always "forbidden" today
    kind: str
    detail: str
    json_pointer: str


@dataclass
class KiroAuditResult:
    forbidden: list[KiroFinding] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.forbidden)


def _shell_blanket_tool(allowed_tools: list) -> str | None:
    for t in allowed_tools:
        if isinstance(t, str) and (t in SHELL_TOOL_NAMES or t in WILDCARD_TOOL_NAMES):
            return t
    return None


def _regex_fullmatch_any(patterns: object, command: str) -> str | None:
    if not isinstance(patterns, list):
        return None
    for pat in patterns:
        if not isinstance(pat, str):
            continue
        try:
            if re.fullmatch(pat, command):
                return pat
        except re.error:
            continue
    return None


def effective_shell_decision(shell_cfg: dict, command: str) -> tuple[str, str | None]:
    """Resolve `command` to ``(decision, matched_pattern)`` — deny before allow."""
    denied = _regex_fullmatch_any(shell_cfg.get("deniedCommands"), command)
    if denied is not None:
        return "deny", denied
    allowed = _regex_fullmatch_any(shell_cfg.get("allowedCommands"), command)
    if allowed is not None:
        return "allow", allowed
    if shell_cfg.get("denyByDefault"):
        return "deny", None
    return "ask", None


def audit_kiro(config: dict) -> KiroAuditResult:
    """Classify a Kiro agent-config dict for dangerous auto-approval."""
    result = KiroAuditResult()

    allowed_tools = config.get("allowedTools") or []
    if not isinstance(allowed_tools, list):
        allowed_tools = []
    tools_settings = config.get("toolsSettings")
    tools_settings = tools_settings if isinstance(tools_settings, dict) else {}
    shell_cfg = tools_settings.get("shell")
    shell_cfg = shell_cfg if isinstance(shell_cfg, dict) else {}

    blanket = _shell_blanket_tool(allowed_tools)
    if blanket is not None:
        result.forbidden.append(
            KiroFinding(
                "forbidden",
                "shell-allow-all",
                f"the shell tool is auto-approved via allowedTools ({blanket!r}) — every shell "
                "command runs with no gate, overriding toolsSettings. Gate it with "
                "toolsSettings.shell (denyByDefault + a scoped allowedCommands allowlist).",
                ".allowedTools",
            )
        )
    else:
        seen: set[str] = set()
        for command, label in DANGEROUS_COMMANDS:
            decision, matched = effective_shell_decision(shell_cfg, command)
            if decision == "allow" and matched is not None and matched not in seen:
                seen.add(matched)
                result.forbidden.append(
                    KiroFinding(
                        "forbidden",
                        "dangerous-allow",
                        f"{label} is auto-approved by allowedCommands rule {matched!r}.",
                        f".toolsSettings.shell.allowedCommands[{matched!r}]",
                    )
                )

    for names, why in EXFIL_TOOLS:
        hit = next((t for t in allowed_tools if isinstance(t, str) and t in names), None)
        if hit is not None:
            result.forbidden.append(
                KiroFinding("forbidden", "exfil-allow", f"{hit!r} {why}.", ".allowedTools")
            )

    web_fetch = tools_settings.get("web_fetch")
    if isinstance(web_fetch, dict):
        for pat in web_fetch.get("trusted") or []:
            if isinstance(pat, str) and pat in _BLANKET_TRUSTED:
                result.forbidden.append(
                    KiroFinding(
                        "forbidden",
                        "exfil-allow",
                        f"web_fetch.trusted blanket-allows every URL ({pat!r}).",
                        ".toolsSettings.web_fetch.trusted",
                    )
                )

    return result
