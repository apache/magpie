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

"""Lint the agent-host sandbox configuration.

Implements mitigation M.29 from
docs/security/threat-model.md: every change to .claude/settings.json
must be acknowledged by an equivalent change to
tools/sandbox-lint/expected.json (the shipped baseline), and the
resulting configuration must satisfy the security invariants encoded
below.

The lint runs in CI on every PR that touches either file. Local edits
made by a maintainer outside a PR cannot be prevented; that residual
is documented in the threat model (residual #4, X3 - Sandbox bypass
via developer override).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = Path(".claude/settings.json")
DEFAULT_EXPECTED = Path("tools/sandbox-lint/expected.json")

# ---------------------------------------------------------------------------
# Security invariants
# ---------------------------------------------------------------------------
#
# These are hard rules that must hold regardless of legitimate edits to
# either file. They guard against the case where a future PR weakens
# both the live settings AND the baseline simultaneously without a
# threat-model review.

# allowRead must not contain any path that resolves to a credential
# store. Each entry is matched with normalised trailing-slash so that
# "~/.aws" and "~/.aws/" both fail.
FORBIDDEN_ALLOW_READ = {
    "~/",
    "/",
    "~/.aws",
    "~/.ssh",
    "~/.netrc",
    "~/.docker",
    "~/.kube",
    "~/.azure",
    "~/.config/gcloud",
}

# allowWrite must be even more restrictive than allowRead. A path
# escaping into any of these would let an agent overwrite credentials
# or shell config.
FORBIDDEN_ALLOW_WRITE = {
    "~/",
    "/",
    "~/.config",
    "~/.config/gh",
    "~/.config/apache-magpie",
    "~/.gnupg",
    "~/.ssh",
    "~/.aws",
    "~/.docker",
    "~/.kube",
}

# permissions.deny must contain at least these entries verbatim. Each
# corresponds to an exfiltration vector documented in the threat model.
REQUIRED_PERMISSIONS_DENY = {
    "Read(~/.aws/**)",
    "Read(~/.ssh/**)",
    "Read(~/.netrc)",
    "Read(~/.docker/**)",
    "Read(~/.kube/**)",
    "Read(~/.config/gh/**)",
    "Read(~/.config/apache-magpie/**)",
    "Read(~/.config/gcloud/**)",
    "Read(~/.azure/**)",
    "Read(//**/.env)",
    "Read(//**/.env.local)",
    "Read(//**/.env.*.local)",
    "Bash(curl *)",
    "Bash(wget *)",
    "Bash(aws *)",
    "Bash(gcloud *)",
    "Bash(az *)",
    "Bash(kubectl *)",
}

# denyRead must contain ~/ as a base deny. Without it, allowRead would
# operate over the full filesystem instead of being an inclusion list
# carved out of a denied home directory.
REQUIRED_DENY_READ = {"~/"}


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------


def _normalise(path: str) -> str:
    """Strip a single trailing slash so '~/.aws' and '~/.aws/' compare equal.

    The sandbox treats both forms as the same directory; the validator
    must too, otherwise the forbidden-list could be bypassed by a
    trailing-slash variant.
    """
    if path.endswith("/") and len(path) > 1:
        return path[:-1]
    return path


def _normalised_set(paths: list[str]) -> set[str]:
    return {_normalise(p) for p in paths}


# ---------------------------------------------------------------------------
# Deep diff — set semantics on known list-typed keys, equality elsewhere
# ---------------------------------------------------------------------------

# Keys whose values are lists treated as sets (order/duplicates do not
# matter for security semantics).
SET_LIST_KEYS = {
    "denyRead",
    "allowRead",
    "allowWrite",
    "allowedDomains",
    "excludedCommands",
    "deny",
    "ask",
}


def deep_diff(actual: Any, expected: Any, path: str = "$") -> list[str]:
    """Return human-readable diff lines; empty list means the two trees match."""
    diffs: list[str] = []
    if type(actual) is not type(expected):
        return [
            f"{path}: type mismatch "
            f"(settings has {type(actual).__name__}, expected has {type(expected).__name__})"
        ]
    if isinstance(actual, dict):
        assert isinstance(expected, dict)
        keys = sorted(set(actual) | set(expected))
        for k in keys:
            if k not in actual:
                diffs.append(f"{path}.{k}: missing in settings (present in expected)")
            elif k not in expected:
                diffs.append(f"{path}.{k}: extra in settings (not in expected)")
            else:
                diffs.extend(deep_diff(actual[k], expected[k], f"{path}.{k}"))
    elif isinstance(actual, list):
        assert isinstance(expected, list)
        leaf = path.rsplit(".", 1)[-1]
        if leaf in SET_LIST_KEYS:
            sa, se = set(actual), set(expected)
            for x in sorted(sa - se):
                diffs.append(f"{path}: extra entry in settings: {x!r}")
            for x in sorted(se - sa):
                diffs.append(f"{path}: missing entry in settings: {x!r}")
        elif actual != expected:
            diffs.append(f"{path}: list mismatch (settings={actual!r}, expected={expected!r})")
    elif actual != expected:
        diffs.append(f"{path}: settings={actual!r} expected={expected!r}")
    return diffs


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------


def check_invariants(settings: dict[str, Any]) -> list[str]:
    """Return list of invariant violations; empty list means OK."""
    errors: list[str] = []

    sandbox = settings.get("sandbox")
    if not isinstance(sandbox, dict):
        return ["sandbox: missing or not an object"]

    if sandbox.get("enabled") is not True:
        errors.append("sandbox.enabled: must be true")

    fs = sandbox.get("filesystem")
    if not isinstance(fs, dict):
        errors.append("sandbox.filesystem: missing or not an object")
    else:
        deny_read = _normalised_set(fs.get("denyRead", []) or [])
        for required in REQUIRED_DENY_READ:
            if _normalise(required) not in deny_read:
                errors.append(
                    f"sandbox.filesystem.denyRead: must contain {required!r} "
                    "(otherwise allowRead expands across the full filesystem)"
                )

        allow_read = _normalised_set(fs.get("allowRead", []) or [])
        for forbidden in FORBIDDEN_ALLOW_READ:
            if _normalise(forbidden) in allow_read:
                errors.append(
                    f"sandbox.filesystem.allowRead: must not contain {forbidden!r} (credential/root path)"
                )

        allow_write = _normalised_set(fs.get("allowWrite", []) or [])
        for forbidden in FORBIDDEN_ALLOW_WRITE:
            if _normalise(forbidden) in allow_write:
                errors.append(
                    f"sandbox.filesystem.allowWrite: must not contain {forbidden!r} "
                    "(would permit credential overwrite)"
                )
        for entry in allow_write - allow_read:
            errors.append(
                f"sandbox.filesystem.allowWrite: contains {entry!r} which is not in allowRead "
                "(allowWrite must be a subset of allowRead)"
            )

    perms = settings.get("permissions")
    if not isinstance(perms, dict):
        errors.append("permissions: missing or not an object")
    else:
        deny = set(perms.get("deny", []) or [])
        for required in REQUIRED_PERMISSIONS_DENY:
            if required not in deny:
                errors.append(f"permissions.deny: must contain {required!r}")

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_json(p: Path) -> dict[str, Any]:
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"sandbox-lint: file not found: {p}") from None
    except json.JSONDecodeError as e:
        raise SystemExit(f"sandbox-lint: invalid JSON in {p}: {e}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"sandbox-lint: top-level value in {p} is not an object")
    return data


def _lint_opencode(config_path: Path) -> int:
    """Lint an OpenCode opencode.json permission policy (invariants only)."""
    from sandbox_lint.opencode import check_opencode_invariants

    config = _load_json(config_path)
    errors = check_opencode_invariants(config)
    if not errors:
        print(f"sandbox-lint: OK ({config_path} permission policy satisfies the OpenCode invariants)")
        return 0
    print(f"sandbox-lint: OpenCode permission-policy violations in {config_path}:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


def _lint_kiro(config_path: Path) -> int:
    """Lint a Kiro CLI agent-config permission policy (invariants only)."""
    from sandbox_lint.kiro import check_kiro_invariants

    config = _load_json(config_path)
    errors = check_kiro_invariants(config)
    if not errors:
        print(f"sandbox-lint: OK ({config_path} permission policy satisfies the Kiro invariants)")
        return 0
    print(f"sandbox-lint: Kiro permission-policy violations in {config_path}:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sandbox-lint",
        description=(
            "Lint .claude/settings.json against the shipped baseline and the "
            "security invariants from docs/security/threat-model.md (M.29); or, "
            "with --opencode, lint an opencode.json permission policy."
        ),
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS,
        help=f"Path to the live settings file (default: {DEFAULT_SETTINGS})",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=DEFAULT_EXPECTED,
        help=f"Path to the canonical baseline (default: {DEFAULT_EXPECTED})",
    )
    parser.add_argument(
        "--opencode",
        type=Path,
        default=None,
        metavar="OPENCODE_JSON",
        help=(
            "Lint an OpenCode opencode.json permission policy against the "
            "OpenCode security invariants instead of the Claude Code sandbox "
            "config (invariants only — no baseline diff)."
        ),
    )
    parser.add_argument(
        "--kiro",
        type=Path,
        default=None,
        metavar="KIRO_AGENT_JSON",
        help=(
            "Lint a Kiro CLI agent-config (.kiro/agents/<name>.json) permission "
            "policy against the Kiro security invariants instead of the Claude "
            "Code sandbox config (invariants only — no baseline diff)."
        ),
    )
    args = parser.parse_args(argv)

    if args.kiro is not None:
        return _lint_kiro(args.kiro)
    if args.opencode is not None:
        return _lint_opencode(args.opencode)

    settings = _load_json(args.settings)
    expected = _load_json(args.expected)

    invariant_errors = check_invariants(settings)
    diff_errors = deep_diff(settings, expected)
    # Run invariants on the baseline too: if a future PR weakens both
    # files in lockstep, the baseline must still pass on its own.
    baseline_invariant_errors = check_invariants(expected)

    if not invariant_errors and not diff_errors and not baseline_invariant_errors:
        print(f"sandbox-lint: OK ({args.settings} matches {args.expected})")
        return 0

    if invariant_errors:
        print(f"sandbox-lint: invariant violations in {args.settings}:", file=sys.stderr)
        for e in invariant_errors:
            print(f"  - {e}", file=sys.stderr)

    if baseline_invariant_errors:
        print(
            f"sandbox-lint: invariant violations in {args.expected} "
            "(the baseline itself is unsafe — fix the baseline before merging):",
            file=sys.stderr,
        )
        for e in baseline_invariant_errors:
            print(f"  - {e}", file=sys.stderr)

    if diff_errors:
        print(
            f"sandbox-lint: {args.settings} differs from {args.expected}. "
            "Every change to the live sandbox must be mirrored in the baseline "
            "(see docs/security/threat-model.md mitigation M.29):",
            file=sys.stderr,
        )
        for e in diff_errors:
            print(f"  - {e}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
