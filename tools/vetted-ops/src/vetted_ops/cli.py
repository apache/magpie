#
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
"""
The dispatcher.

``vetted-op --caller <name> <operation> [param …]``       (reads and writes)
``vetted-op-read --caller <name> <operation> [param …]``  (reads only, by construction)

Everything the caller supplies is a *parameter*, never a fragment of a command.
The operation name selects a builder from the closed catalogue; the builder
returns an argv list; the argv list is executed without a shell. There is no
path by which a parameter becomes an argument to ``gh`` that the catalogue did
not put there.

**Where the privilege boundary is, and where it is not.** ``--caller`` is an
argv string chosen by whoever runs the command. If that is an agent, the agent
picks its own caller name, so ``--caller`` scopes a *cooperating* skill to least
privilege — it is not a boundary against a confused or hostile one, and must
never be described as one.

The boundary is the **entry point**, because the entry point is what a harness
permission rule keys on and argv cannot change which binary is running.
``vetted-op-read`` refuses every write operation in the catalogue before it
looks at policy at all, so it is safe to allowlist outright. ``vetted-op`` can
write and therefore has to keep whatever confirmation the harness puts in front
of it. Splitting them is the whole point: it lets the read path lose its prompts
without the write path losing its gate.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from . import ops as ops_mod
from .config import Config, ConfigError, describe, load

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3
EXIT_COMMAND = 4


def _validate_params(
    op: ops_mod.Op, values: list[str], config: Config
) -> tuple[dict[str, str], bytes | None]:
    if len(values) != len(op.params):
        raise ops_mod.ParamError(
            f"operation {op.name!r} takes {len(op.params)} parameter(s) "
            f"({', '.join(op.params) or 'none'}), got {len(values)}"
        )

    resolved: dict[str, str] = {}
    body: bytes | None = None
    for name, raw in zip(op.params, values, strict=True):
        # A parameter is never an option. Rejecting a leading dash removes the
        # whole class of "smuggle a flag into gh" tricks before any validator
        # even runs.
        if raw.startswith("-"):
            raise ops_mod.ParamError(f"parameter {name!r} may not start with '-': {raw!r}")

        if name in op.enums:
            resolved[name] = ops_mod.enum(config.enum_values(op.enums[name]))(raw)
        elif name in op.body_files:
            # Read the content here and hand `gh` a "-" so it takes the body on
            # stdin. The bytes that were validated are then, necessarily, the
            # bytes that get published — there is no second open to race.
            if body is not None:
                raise ops_mod.ParamError(
                    f"operation {op.name!r} declares more than one body parameter; "
                    f"the dispatcher pipes exactly one body on stdin"
                )
            body = ops_mod.read_body(raw, workspace=config.workspace)
            resolved[name] = "-"
        elif name in {"number", "comment_id", "run_id"}:
            resolved[name] = ops_mod.number(raw)
        elif name in {"ref", "base", "head", "prefix"}:
            resolved[name] = ops_mod.ref(raw)
        elif name == "path":
            resolved[name] = ops_mod.repo_path(raw)
        elif name == "login":
            resolved[name] = ops_mod.login(raw)
        elif name == "ghsa":
            resolved[name] = ops_mod.ghsa(raw)
        elif name == "item_id":
            resolved[name] = ops_mod.node_id(raw)
        else:  # pragma: no cover - guarded by the catalogue test
            raise ops_mod.ParamError(f"operation {op.name!r} declares unknown parameter {name!r}")
    return resolved, body


def build_argv(op: ops_mod.Op, params: dict[str, str], config: Config) -> list[str]:
    argv = op.build(config.as_mapping(), **params)
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise ops_mod.ParamError(f"operation {op.name!r} produced a malformed argv")
    if argv[0] != "gh":
        raise ops_mod.ParamError(f"operation {op.name!r} tried to run {argv[0]!r}, not gh")
    return argv


def _reject_repeated_caller(argv: Sequence[str]) -> None:
    """
    Refuse a second ``--caller``.

    argparse keeps the last occurrence, so ``--caller read-only … --caller
    privileged`` resolves to the privileged one while still matching a
    permission rule written against the read-only prefix. That turns a
    prefix-matched allow rule into a bypass, so repetition is an error rather
    than a last-wins convenience.
    """
    seen = sum(1 for a in argv if a == "--caller" or a.startswith("--caller="))
    if seen > 1:
        raise ops_mod.ParamError(
            "--caller given more than once; it selects the policy entry and must be unambiguous"
        )


def main(argv: list[str] | None = None, *, read_only: bool = False) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    prog = "vetted-op-read" if read_only else "vetted-op"
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Run one fixed, policy-scoped read operation. No pass-through arguments."
            if read_only
            else "Run one fixed, policy-scoped GitHub operation. No pass-through arguments."
        ),
    )
    parser.add_argument("--caller", help="the skill or plugin invoking this operation")
    parser.add_argument("--config", type=Path, default=None, help="path to the policy TOML")
    parser.add_argument("--dry-run", action="store_true", help="print the argv that would run, then exit")
    parser.add_argument("operation", nargs="?", help="operation name, or 'list-ops' / 'policy'")
    parser.add_argument("params", nargs="*", help="operation parameters, positionally")
    args = parser.parse_args(argv)

    if args.operation in (None, "list-ops"):
        for name, op in sorted(ops_mod.OPS.items()):
            if read_only and op.writes:
                continue
            kind = "write" if op.writes else "read "
            print(f"{kind}  {name:<22} {' '.join(op.params)}\n        {op.summary}")
        return EXIT_OK

    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"vetted-op: config error: {exc}", file=sys.stderr)
        return EXIT_POLICY

    if args.operation == "policy":
        print(describe(config))
        return EXIT_OK

    if not args.caller:
        print("vetted-op: --caller is required for any operation", file=sys.stderr)
        return EXIT_USAGE

    try:
        _reject_repeated_caller(raw)
        op = ops_mod.resolve(args.operation)
        # Deliberately ahead of the policy lookup. This refusal does not depend
        # on the config, on --caller, or on anything else the invoker chose: on
        # this entry point a write operation does not exist. That is what makes
        # the entry point allowlistable when `vetted-op` is not.
        if read_only and op.writes:
            raise ops_mod.ParamError(
                f"{op.name!r} writes, and this is the read-only dispatcher; "
                f"run it through 'vetted-op', which stays behind confirmation"
            )
        permitted = config.ops_for(args.caller)
        if op.name not in permitted:
            raise ops_mod.ParamError(
                f"caller {args.caller!r} is not permitted to run {op.name!r}; "
                f"permitted: {', '.join(sorted(permitted)) or '(none)'}"
            )
        params, body = _validate_params(op, list(args.params), config)
        command = build_argv(op, params, config)
    except (ops_mod.ParamError, ConfigError) as exc:
        print(f"vetted-op: refused: {exc}", file=sys.stderr)
        return EXIT_POLICY

    if args.dry_run:
        print(" ".join(command))
        return EXIT_OK

    # No shell. The argv list is passed through verbatim, and any body travels
    # on stdin as bytes we already read — `gh` opens no file of ours.
    completed = subprocess.run(command, check=False, input=body)
    if completed.returncode != EXIT_OK:
        print(f"vetted-op: {op.name} failed (gh exit {completed.returncode})", file=sys.stderr)
        return EXIT_COMMAND
    return EXIT_OK


def main_read(argv: list[str] | None = None) -> int:
    """The `vetted-op-read` console script: `main`, with writes made unreachable."""
    return main(argv, read_only=True)
