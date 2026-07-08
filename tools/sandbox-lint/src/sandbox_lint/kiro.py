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

"""Security invariants for a Kiro CLI agent-config permission policy.

Like the OpenCode lint, this asserts safety properties (no baseline diff) —
an adopter's `.kiro/agents/<name>.json` is their own. The intent is identical
to the Claude Code and OpenCode lints: the config must not **auto-approve
dangerous shell execution or exfiltration surfaces**.

Kiro's permission model differs in shape from OpenCode's per-command
`permission.bash` decision map. Kiro resolves a shell command through
(<https://kiro.dev/docs/cli/reference/built-in-tools#execute-shell-commands>):

1. If the shell tool (`shell` / `execute_bash` / `execute_cmd`), `*`, or
   `@builtin` is in `allowedTools`, **every** shell command is auto-approved
   with no gate (and this overrides `toolsSettings`).
2. Otherwise, per command: `deniedCommands` regex (evaluated first) → deny;
   `allowedCommands` regex → allow; `autoAllowReadonly` + read-only → allow;
   `denyByDefault` → deny; else → **ask** (prompt).

`allowedCommands` / `deniedCommands` are full-string-anchored regex (`\\A..\\z`,
no look-around), so a command is matched with :func:`re.fullmatch`.

Unlike OpenCode, a **missing** shell policy is *not* flagged: Kiro's default is
to prompt for `shell`, which is already safe. The danger is only in configs
that add auto-approval. `autoAllowReadonly` is not probed — Kiro classifies
read-only-ness itself and none of the dangerous families below are read-only.
"""

from __future__ import annotations

import re
from typing import Any

from sandbox_lint.opencode import DANGEROUS_COMMANDS

# Tool ids that, in `allowedTools`, auto-approve every shell command.
SHELL_TOOL_NAMES = frozenset({"shell", "execute_bash", "execute_cmd"})
WILDCARD_TOOL_NAMES = frozenset({"*", "@builtin"})

# Non-shell tools whose presence in `allowedTools` is an exfiltration /
# credential-access risk when auto-approved.
EXFIL_TOOLS: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"web_fetch", "webfetch"}), "auto-approves fetching arbitrary URLs (exfiltration channel)"),
    (frozenset({"aws", "use_aws"}), "auto-approves AWS CLI calls (cloud credentials)"),
)


def _shell_blanket_allowed(allowed_tools: list[Any]) -> bool:
    return any(t in SHELL_TOOL_NAMES or t in WILDCARD_TOOL_NAMES for t in allowed_tools if isinstance(t, str))


def _regex_fullmatch_any(patterns: Any, command: str) -> str | None:
    """Return the first pattern that fully matches `command`, or None.

    Mirrors Kiro's `\\A..\\z`-anchored regex semantics via ``re.fullmatch``.
    Invalid patterns are skipped (Kiro would reject them at load time).
    """
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


def effective_shell_decision(shell_cfg: dict[str, Any], command: str) -> tuple[str, str | None]:
    """Resolve `command` to (decision, matched_pattern) — deny before allow."""
    denied = _regex_fullmatch_any(shell_cfg.get("deniedCommands"), command)
    if denied is not None:
        return "deny", denied
    allowed = _regex_fullmatch_any(shell_cfg.get("allowedCommands"), command)
    if allowed is not None:
        return "allow", allowed
    if shell_cfg.get("denyByDefault"):
        return "deny", None
    return "ask", None


def check_kiro_invariants(config: dict[str, Any]) -> list[str]:
    """Return a list of invariant violations; empty means the policy is safe."""
    errors: list[str] = []

    allowed_tools = config.get("allowedTools") or []
    if not isinstance(allowed_tools, list):
        allowed_tools = []
    tools_settings = config.get("toolsSettings")
    tools_settings = tools_settings if isinstance(tools_settings, dict) else {}
    shell_cfg = tools_settings.get("shell")
    shell_cfg = shell_cfg if isinstance(shell_cfg, dict) else {}

    # #2 — blanket auto-approve of the shell tool via allowedTools.
    if _shell_blanket_allowed(allowed_tools):
        errors.append(
            'allowedTools: must not auto-approve the shell tool (contains "shell"/'
            '"execute_bash"/"*"/"@builtin") — every shell command runs with no gate, '
            "and this overrides toolsSettings.shell. Remove it and gate shell via "
            "toolsSettings.shell (denyByDefault + a scoped allowedCommands allowlist)."
        )
    else:
        # #4 — specific allowedCommands rules that auto-approve a dangerous family.
        seen: set[str] = set()
        for command, label in DANGEROUS_COMMANDS:
            decision, matched = effective_shell_decision(shell_cfg, command)
            if decision == "allow" and matched is not None and matched not in seen:
                seen.add(matched)
                errors.append(
                    f"toolsSettings.shell.allowedCommands: must not auto-approve {label} "
                    f"(rule {matched!r} matches and is not denied)"
                )

    # #5 — exfil / credential tools blanket-allowed via allowedTools.
    for names, why in EXFIL_TOOLS:
        hit = next((t for t in allowed_tools if isinstance(t, str) and t in names), None)
        if hit is not None:
            errors.append(f"allowedTools: must not contain {hit!r} — it {why}; gate it instead")

    # web_fetch.trusted must not blanket-allow every URL.
    web_fetch = tools_settings.get("web_fetch")
    if isinstance(web_fetch, dict):
        for pat in web_fetch.get("trusted") or []:
            if isinstance(pat, str) and pat in (".*", ".+", "^.*$", "(.*)"):
                errors.append(
                    f"toolsSettings.web_fetch.trusted: must not be a blanket {pat!r} — "
                    "it auto-allows fetching any URL (exfiltration channel)"
                )

    return errors
