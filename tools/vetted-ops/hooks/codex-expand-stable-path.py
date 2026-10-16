#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Codex PreToolUse hook: spell the vetted-ops stable path absolute.

Skills invoke the dispatcher as ``uv run --project ~/.claude/magpie/vetted-ops
...`` (or ``uvx --from``). Codex execpolicy never matches that spelling: its
plain-command parser rejects a word containing ``~``, and a native rule naming
``~`` would be unsafe, because the shell resolves ``~`` from ``HOME`` (which an
earlier command can reassign) and ``uv`` itself treats ``~`` as a relative
directory. The rules therefore name only the absolute path.

This hook closes the gap before the policy runs, for reads only: when the
whole command is exactly one ``vetted-op-read`` call in that spelling, with
plain or simply quoted arguments, it rewrites the path to the absolute stable
path. Anything chained, redirected, substituted or spanning lines is left
alone, and so are the write entry points, which must always prompt.
``vetted-ops-codex-rules --hook`` renders the registration with
``--stable-path`` set to the path it writes into the rules, so the two cannot
disagree; only without that argument does the home directory come from the
password database (never from ``HOME``).

Codex requires ``permissionDecision: "allow"`` to carry ``updatedInput``. In
Codex 0.163 that only applies the rewrite: a hook result is either continue,
with an optional rewrite, or blocked, and the rewritten command then goes
through the native rules and approval. Because the hook acts only on a lone
read the rules already allow, even a reading of ``allow`` as an approval could
approve nothing more. Claude Code does read the field as a permission grant,
so register this hook in Codex configuration only; as a backstop it stays
silent unless the event carries the ``turn_id`` and ``model`` fields Codex
sends.
"""

from __future__ import annotations

import json
import os
import pwd
import re
import shlex
import sys

STABLE_SUFFIX = ".claude/magpie/vetted-ops"
# One whole command: a launcher, the `~` stable path, the read entry point, then
# only plain words or quoted strings with nothing the shell would expand.
_ARG = r"""(?:[^\s'"\\;&|<>()`$~*?\[\]{}#!^]+|'[^'\n]*'|"[^"$`\\\n]*")"""
_LONE_READ = re.compile(
    r"(?P<launcher>uv run --project|uvx --from) ~/\.claude/magpie/vetted-ops vetted-op-read"
    rf"(?P<args>(?:[ \t]+{_ARG})*)[ \t]*"
)


def stable_path() -> str:
    """The installed stable path under the account's home from passwd."""
    return os.path.join(pwd.getpwuid(os.getuid()).pw_dir, STABLE_SUFFIX)


def rewrite(command: str, absolute: str | None = None) -> str:
    """Return ``command`` with its path made absolute if it is a lone read call."""
    match = _LONE_READ.fullmatch(command.strip())
    if match is None:
        return command
    path = shlex.quote(absolute or stable_path())
    return f"{match['launcher']} {path} vetted-op-read{match['args']}"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    absolute = args[1] if len(args) == 2 and args[0] == "--stable-path" and os.path.isabs(args[1]) else None
    try:
        event = json.load(sys.stdin)
        command = event["tool_input"]["command"]
        if "turn_id" not in event or "model" not in event:
            return 0
    except (ValueError, KeyError, TypeError):
        return 0
    if not isinstance(command, str):
        return 0
    rewritten = rewrite(command, absolute)
    if rewritten != command:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": {"command": rewritten},
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
