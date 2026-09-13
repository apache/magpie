# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Static checks for Magpie's Gemini profile, not an effective-policy evaluator."""

from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_COMMANDS = (
    "git status",
    "git status --short",
    "git status --porcelain",
    "git status -sb",
    "git diff --stat",
    "git log --oneline",
    "git ls-files",
    "gh auth status",
)
ALLOWED_GH_PREFIXES = (
    "gh pr view",
    "gh pr list",
    "gh pr diff",
    "gh pr checks",
    "gh pr status",
    "gh issue view",
    "gh issue list",
    "gh issue status",
    "gh repo view",
    "gh repo list",
    "gh run view",
    "gh run list",
    "gh run watch",
    "gh workflow view",
    "gh workflow list",
    "gh release view",
    "gh release list",
    "gh label list",
    "gh cache list",
    "gh search",
)
READ_ARGS_PATTERN = '"command":"(?:' + "|".join(ALLOWED_COMMANDS) + ')"'
READ_GH_ARGS_PATTERN = r'"command":"(?:' + "|".join(ALLOWED_GH_PREFIXES) + r')(?:"| [^"\\<>;&|`$]*")'

DENIED_COMMANDS = (
    "curl",
    "wget",
    "aws",
    "gcloud",
    "az",
    "kubectl",
    "docker login",
    "npm publish",
    "pip install --upgrade",
    "uv self update",
    "gh auth token",
    "gh auth refresh",
)
NATIVE_TOOLS = (
    "read_file",
    "read_many_files",
    "list_directory",
    "glob",
    "grep_search",
    "write_file",
    "replace",
)
PROTECTED_PATHS = (
    ".aws/credentials",
    ".ssh/id_rsa",
    ".docker/config.json",
    ".kube/config",
    ".azure/token",
    ".gnupg/key",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".config/gh/hosts.yml",
    ".config/gcloud/token",
    ".config/apache-magpie/gmail-oauth.json",
    ".gemini/oauth_creds.json",
    ".gemini/google_accounts.json",
    ".gemini/settings.json",
    ".gemini/policies/override.toml",
    ".env",
    ".env.local",
    ".env.production.local",
)


def _names(value: Any) -> list[str]:
    return [value] if isinstance(value, str) else value if isinstance(value, list) else []


def check_gemini_invariants(settings: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    """Check shipped settings and representative rule coverage.

    Regex checks use the common Python/JavaScript subset of the shipped patterns.
    They do not model Gemini's tiers, shell parser, trust state, or user settings;
    the separate native probe exercises the actual runtime.
    """
    errors: list[str] = []
    required: dict[str, dict[str, Any]] = {
        "general": {"defaultApprovalMode": "default"},
        "security": {
            "toolSandboxing": True,
            "disableYoloMode": True,
            "disableAlwaysAllow": True,
            "enablePermanentToolApproval": False,
        },
        "tools": {"sandboxAllowedPaths": [], "sandboxNetworkAccess": False},
    }
    for section, values in required.items():
        actual = settings.get(section)
        for key, expected in values.items():
            if (
                not isinstance(actual, dict)
                or type(actual.get(key)) is not type(expected)
                or actual[key] != expected
            ):
                errors.append(f"settings.json: {section}.{key} must be {expected!r}")
    security = settings.get("security", {})
    redaction = security.get("environmentVariableRedaction", {}) if isinstance(security, dict) else {}
    if not isinstance(redaction, dict) or redaction.get("enabled") is not True:
        errors.append("settings.json: security.environmentVariableRedaction.enabled must be true")
    tools = settings.get("tools", {})
    if isinstance(tools, dict) and tools.get("sandbox") not in (None, False):
        errors.append(
            "settings.json: tools.sandbox selects a different, legacy sandbox; use security.toolSandboxing"
        )
    paths = settings.get("policyPaths", [])
    if not isinstance(paths, list) or "~/.gemini/policies" not in paths:
        errors.append("settings.json: policyPaths must retain ~/.gemini/policies")
    if not isinstance(paths, list) or not any(
        p in paths for p in (".gemini/policies/magpie.toml", "./.gemini/policies/magpie.toml")
    ):
        errors.append("settings.json: policyPaths must explicitly load .gemini/policies/magpie.toml")

    rules = policy.get("rule", [])
    if not isinstance(rules, list) or not all(isinstance(r, dict) for r in rules):
        return [*errors, "magpie.toml: rule must be an array of tables"]
    active = []
    for rule in rules:
        if rule.get("decision") not in ("allow", "ask_user", "deny"):
            errors.append("magpie.toml: decision must be allow, ask_user, or deny")
        priority = rule.get("priority")
        if type(priority) is not int or not 0 <= priority <= 999:
            errors.append("magpie.toml: each rule needs an integer priority from 0 to 999")
            continue
        if priority == 950:
            errors.append("magpie.toml: priority 950 is reserved for remembered approvals and can be skipped")
        if any(k in rule for k in ("modes", "interactive", "subagent", "toolAnnotations")):
            continue  # Conditional rules cannot satisfy the all-mode baseline.
        active.append(rule)

    expected_allows = [
        {
            "toolName": "run_shell_command",
            "argsPattern": READ_ARGS_PATTERN,
            "decision": "allow",
            "priority": 700,
        },
        {
            "toolName": "run_shell_command",
            "argsPattern": READ_GH_ARGS_PATTERN,
            "decision": "allow",
            "priority": 700,
        },
    ]
    actual_allows = [r for r in rules if r.get("decision") == "allow"]
    for rule in actual_allows:
        if rule not in expected_allows:
            errors.append("magpie.toml: allow rules must use the reviewed scoped reads without extra grants")
    for rule in expected_allows:
        if rule not in actual_allows:
            errors.append("magpie.toml: missing scoped read allow (priority 700)")

    def asks(tool: str, *, mcp: bool = False) -> bool:
        for rule in active:
            if rule.get("decision") != "ask_user" or tool not in _names(rule.get("toolName")):
                continue
            expected = {"argsPattern": '"command":'} if tool == "run_shell_command" else {}
            if mcp:
                expected["mcpName"] = "*"
            if all(
                rule.get(k) == expected.get(k)
                for k in ("argsPattern", "commandPrefix", "commandRegex", "mcpName")
            ):
                return True
        return False

    for tool in ("run_shell_command", "write_file", "replace"):
        if not asks(tool):
            errors.append(
                f"magpie.toml: missing all-mode {tool} ask_user rule (shell requires the command argument matcher)"
            )
    if not asks("*", mcp=True):
        errors.append("magpie.toml: missing all-server MCP ask_user rule")

    ask_priority = max((r["priority"] for r in active if r.get("decision") == "ask_user"), default=-1)
    for tool in ("run_shell_command", "write_file", "replace", "*"):
        if not any(
            tool in _names(r.get("toolName"))
            and r.get("modes") == ["plan"]
            and r.get("decision") == "deny"
            and type(r.get("priority")) is int
            and ask_priority < r["priority"] < 700
            and r.get("mcpName") == ("*" if tool == "*" else None)
            and not any(
                k in r
                for k in (
                    "argsPattern",
                    "commandPrefix",
                    "commandRegex",
                    "interactive",
                    "subagent",
                    "toolAnnotations",
                )
            )
            for r in rules
        ):
            errors.append(
                f"magpie.toml: missing Plan Mode deny for {tool} between fallback asks and scoped reads"
            )
    denies = [
        r
        for r in active
        if r.get("decision") == "deny" and r["priority"] > max(ask_priority, 700) and "mcpName" not in r
    ]
    for command in DENIED_COMMANDS:
        if not any(
            "run_shell_command" in _names(r.get("toolName"))
            and command in _names(r.get("commandPrefix"))
            and "argsPattern" not in r
            and "commandRegex" not in r
            for r in denies
        ):
            errors.append(f"magpie.toml: missing higher-priority deny for {command}")
    for tool in NATIVE_TOOLS:
        patterns = []
        for rule in denies:
            if tool in _names(rule.get("toolName")) and isinstance(rule.get("argsPattern"), str):
                try:
                    patterns.append(re.compile(rule["argsPattern"]))
                except re.error:
                    errors.append(f"magpie.toml: invalid argsPattern for {tool}")
        samples = list(PROTECTED_PATHS)
        if tool in ("write_file", "replace"):
            samples += [".gemini/hooks/script.py", ".geminiignore", "GEMINI.md", "AGENTS.md"]
        for path in samples:
            if not any(p.search(json.dumps({"file_path": path})) for p in patterns):
                errors.append(f"magpie.toml: missing native {tool} deny for {path}")
    return errors
