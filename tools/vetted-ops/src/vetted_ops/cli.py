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

``vetted-op --caller <name> <operation> [param …]``

Everything the caller supplies is a *parameter*, never a fragment of a command.
The operation name selects a builder from the closed catalogue; the builder
returns an argv list; the argv list is executed without a shell. There is no
path by which a parameter becomes an argument to ``gh`` that the catalogue did
not put there.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import ops as ops_mod
from .config import Config, ConfigError, describe, load

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3
EXIT_COMMAND = 4


def _validate_params(op: ops_mod.Op, values: list[str], config: Config) -> dict[str, str]:
    if len(values) != len(op.params):
        raise ops_mod.ParamError(
            f"operation {op.name!r} takes {len(op.params)} parameter(s) "
            f"({', '.join(op.params) or 'none'}), got {len(values)}"
        )

    resolved: dict[str, str] = {}
    for name, raw in zip(op.params, values, strict=True):
        # A parameter is never an option. Rejecting a leading dash removes the
        # whole class of "smuggle a flag into gh" tricks before any validator
        # even runs.
        if raw.startswith("-"):
            raise ops_mod.ParamError(f"parameter {name!r} may not start with '-': {raw!r}")

        if name in op.enums:
            resolved[name] = ops_mod.enum(config.enum_values(op.enums[name]))(raw)
        elif name in op.body_files:
            resolved[name] = ops_mod.body_file(raw, workspace=config.workspace)
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
    return resolved


def build_argv(op: ops_mod.Op, params: dict[str, str], config: Config) -> list[str]:
    argv = op.build(config.as_mapping(), **params)
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise ops_mod.ParamError(f"operation {op.name!r} produced a malformed argv")
    if argv[0] != "gh":
        raise ops_mod.ParamError(f"operation {op.name!r} tried to run {argv[0]!r}, not gh")
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vetted-op",
        description="Run one fixed, policy-scoped GitHub operation. No pass-through arguments.",
    )
    parser.add_argument("--caller", help="the skill or plugin invoking this operation")
    parser.add_argument("--config", type=Path, default=None, help="path to the policy TOML")
    parser.add_argument("--dry-run", action="store_true", help="print the argv that would run, then exit")
    parser.add_argument("operation", nargs="?", help="operation name, or 'list-ops' / 'policy'")
    parser.add_argument("params", nargs="*", help="operation parameters, positionally")
    args = parser.parse_args(argv)

    if args.operation in (None, "list-ops"):
        for name, op in sorted(ops_mod.OPS.items()):
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
        op = ops_mod.resolve(args.operation)
        permitted = config.ops_for(args.caller)
        if op.name not in permitted:
            raise ops_mod.ParamError(
                f"caller {args.caller!r} is not permitted to run {op.name!r}; "
                f"permitted: {', '.join(sorted(permitted)) or '(none)'}"
            )
        params = _validate_params(op, list(args.params), config)
        command = build_argv(op, params, config)
    except (ops_mod.ParamError, ConfigError) as exc:
        print(f"vetted-op: refused: {exc}", file=sys.stderr)
        return EXIT_POLICY

    if args.dry_run:
        print(" ".join(command))
        return EXIT_OK

    # No shell. The argv list is passed through verbatim.
    completed = subprocess.run(command, check=False)
    if completed.returncode != EXIT_OK:
        print(f"vetted-op: {op.name} failed (gh exit {completed.returncode})", file=sys.stderr)
        return EXIT_COMMAND
    return EXIT_OK
