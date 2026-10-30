# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Static checks for Magpie's user-scope Antigravity profile.

The profile is the user's ``~/.gemini/antigravity-cli/settings.json`` plus the
guard registration in ``~/.gemini/config/hooks.json``; the framework ships both
under ``tools/agent-isolation/antigravity/``. The required ask and deny rules are
derived from the Claude Code reference baseline (``expected.json``), so the two
profiles cannot drift apart. This is not an effective-policy evaluator: it does
not model Antigravity's rule matching, the account's permission preset, or a
running session.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TOOL_PERMISSIONS = ("proceed-in-sandbox", "request-review", "strict")
AGENT_MODES = (None, "default", "plan")
GH_API_MUTATION = "command(regex:^gh api( .*)? (-X|-f|-F|--method|--field|--raw-field|--input))"
GUARD_SUFFIX = re.compile(r"""agent_guard/__init__\.py"?\s+--antigravity\s*$""")
# Agent-writable files that would let the agent change its own permissions,
# hooks, MCP servers, global skills and rules, or the vetted-ops grants.
CONFIG_WRITE_DENIES = (
    "write_file(~/.gemini/antigravity-cli/settings.json)",
    "write_file(~/.gemini/antigravity-cli/plugins)",
    "write_file(~/.gemini/antigravity-cli/skills)",
    "write_file(~/.gemini/antigravity-cli/rules)",
    "write_file(~/.gemini/config)",
    "write_file(.agents/hooks.json)",
    "write_file(.agents/mcp_config.json)",
    "write_file(.agents/rules.json)",
    "write_file(.agent/hooks.json)",
    "write_file(.agent/mcp_config.json)",
    "write_file(.agent/rules.json)",
    "write_file(.apache-magpie-overrides/tools/vetted-ops)",
)
ENV_READ_DENIES = ("read_file(.env)", "read_file(.env.local)")
# Wildcard grants that remove a whole approval namespace.
BROAD_ALLOWS = (
    "command(*)",
    "unsandboxed(*)",
    "read_file(*)",
    "write_file(*)",
    "read_url(*)",
    "execute_url(*)",
    "mcp(*)",
)


def _command(rule: str) -> str | None:
    match = re.fullmatch(r"Bash\((.*?)\s?\*?\)", rule)
    return match.group(1).strip() if match else None


def required_rules(baseline: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Map the Claude baseline's denies and asks to Antigravity rule strings.

    ``Read(~/.x/**)`` becomes ``read_file(~/.x)``, ``Bash(cmd *)`` becomes
    ``command(cmd)``; the ``gh api`` mutation forms collapse into one regex
    rule, and Claude-specific vetted-ops paths are skipped.
    """
    permissions = baseline.get("permissions", {})
    deny: list[str] = []
    for rule in permissions.get("deny", []):
        if rule.startswith("Read(~/"):
            deny.append("read_file(" + rule[5:-1].removesuffix("/**") + ")")
        elif (command := _command(rule)) is not None:
            deny.append(f"command({command})")
    deny += [*ENV_READ_DENIES, *CONFIG_WRITE_DENIES]
    ask: list[str] = []
    for rule in permissions.get("ask", []):
        command = _command(rule)
        if command is None or "~/.claude" in command:
            continue
        mapped = (
            GH_API_MUTATION
            if command.startswith("gh api")
            else f"command({re.sub(r' --force(-with-lease)?$', '', command)})"
        )
        if mapped not in ask:
            ask.append(mapped)
    return deny, ask


def _rules(settings: dict[str, Any], key: str, home: str) -> list[Any]:
    permissions = settings.get("permissions")
    values = permissions.get(key) if isinstance(permissions, dict) else None
    if not isinstance(values, list):
        return []
    # The install merge writes absolute home paths; compare in the shipped ~/ form.
    return [v.replace(f"({home}/", "(~/") if isinstance(v, str) else v for v in values]


def check_antigravity_settings(
    settings: dict[str, Any], baseline: dict[str, Any], home: str | None = None, *, live: bool = False
) -> list[str]:
    """Check the sandbox, approval mode, and rule coverage of ``settings.json``.

    ``live`` marks the user's installed profile rather than the shipped
    template. Antigravity matches absolute or workspace-relative paths and
    whether it expands ``~`` is unverified, so a live ``~/`` rule may enforce
    nothing: it is an error there, and only the absolute form satisfies the
    required rules.
    """
    home = home or str(Path.home())
    errors: list[str] = []
    if live:
        permissions = settings.get("permissions")
        for key in ("allow", "ask", "deny"):
            values = permissions.get(key) if isinstance(permissions, dict) else None
            for rule in values if isinstance(values, list) else []:
                if isinstance(rule, str) and "(~/" in rule:
                    errors.append(
                        f"settings.json: permissions.{key} rule {rule} uses ~/; write the absolute path "
                        f"({rule.replace('(~/', f'({home}/')})"
                    )
    if settings.get("enableTerminalSandbox") is not True:
        errors.append("settings.json: enableTerminalSandbox must be true")
    if settings.get("toolPermission") not in TOOL_PERMISSIONS:
        errors.append(f"settings.json: toolPermission must be one of {', '.join(TOOL_PERMISSIONS)}")
    if settings.get("allowNonWorkspaceAccess") is not False:
        errors.append("settings.json: allowNonWorkspaceAccess must be false")
    if settings.get("agentMode") not in AGENT_MODES:
        errors.append(
            "settings.json: agentMode must be unset, default or plan; "
            "accept-edits and auto approve edits or commands without review"
        )

    allow = _rules(settings, "allow", home)
    ask = _rules(settings, "ask", home)
    deny = _rules(settings, "deny", home)
    for rule in allow:
        if not isinstance(rule, str):
            errors.append("settings.json: permissions.allow entries must be strings")
        elif rule in BROAD_ALLOWS or rule.startswith("unsandboxed("):
            errors.append(f"settings.json: permissions.allow must not grant {rule}")
    required_deny, required_ask = required_rules(baseline)
    errors += [f"settings.json: permissions.deny is missing {r}" for r in required_deny if r not in deny]
    errors += [f"settings.json: permissions.ask is missing {r}" for r in required_ask if r not in ask]
    return errors


def check_antigravity_hooks(hooks: dict[str, Any]) -> list[str]:
    """Check for exactly one enabled guard registration on ``run_command``."""
    guards = 0
    for config in hooks.values():
        if not isinstance(config, dict) or config.get("enabled") is False:
            continue
        for group in config.get("PreToolUse", []) or []:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher", "")
            if not isinstance(matcher, str) or not (
                matcher in ("", "*") or re.fullmatch(matcher, "run_command")
            ):
                continue
            for hook in group.get("hooks", []) or []:
                command = hook.get("command") if isinstance(hook, dict) else None
                if isinstance(command, str) and GUARD_SUFFIX.search(command):
                    guards += 1
    if guards == 1:
        return []
    return [
        f"hooks.json: expected exactly one enabled PreToolUse guard on run_command "
        f"running agent_guard/__init__.py --antigravity, found {guards}"
    ]
