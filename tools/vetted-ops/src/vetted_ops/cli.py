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
``vetted-op-tracker --caller <name> <operation> [param …]``  (tracker procedures only, by construction)

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

``vetted-op-tracker`` applies the same idea to the sandbox rather than to the
prompt. It refuses everything except the ``procedure`` operations — the status
rollup and body-field procedures, whose runner refuses any ``gh`` call outside
``repos/<tracker>/`` — so it can be excluded from the sandbox (where ``gh``
cannot verify TLS) while its writes keep their confirmation.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from . import ops as ops_mod
from . import procedures
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
        elif name == "team":
            resolved[name] = ops_mod.team(raw)
        elif name == "title":
            resolved[name] = ops_mod.title(raw)
        elif name == "ghsa":
            resolved[name] = ops_mod.ghsa(raw)
        elif name in {"item_id", "content_id"}:
            resolved[name] = ops_mod.node_id(raw)
        elif name == "vuln_id":
            resolved[name] = ops_mod.vuln_id(raw)
        elif name == "package_name":
            resolved[name] = ops_mod.package_name(raw)
        elif name == "version":
            resolved[name] = ops_mod.version(raw)
        elif name == "commit_hash":
            resolved[name] = ops_mod.commit_hash(raw)
        elif name == "cve_id":
            resolved[name] = ops_mod.cve_id(raw)
        elif name == "action":
            resolved[name] = ops_mod.action(raw)
        elif name == "field":
            resolved[name] = ops_mod.field_name(raw)
        else:  # pragma: no cover - guarded by the catalogue test
            raise ops_mod.ParamError(f"operation {op.name!r} declares unknown parameter {name!r}")
    return resolved, body


def build_argv(
    op: ops_mod.Op, params: dict[str, str], config: Config
) -> list[str] | dict[str, object] | procedures.Plan:
    result = op.build(config.as_mapping(), **params)
    if op.backend == "gh":
        if not isinstance(result, list) or not all(isinstance(a, str) for a in result):
            raise ops_mod.ParamError(f"operation {op.name!r} produced a malformed argv")
        if result[0] != "gh":
            raise ops_mod.ParamError(f"operation {op.name!r} tried to run {result[0]!r}, not gh")
    elif op.backend == "http-read":
        if not isinstance(result, dict):
            raise ops_mod.ParamError(f"operation {op.name!r} produced a malformed request descriptor")
    elif op.backend == "procedure":
        if not isinstance(result, procedures.Plan):
            raise ops_mod.ParamError(f"operation {op.name!r} produced a malformed procedure plan")
        if result.tracker != config.tracker_repo:
            raise ops_mod.ParamError(f"operation {op.name!r} planned against a repo other than the tracker")
    else:
        raise ops_mod.ParamError(f"operation {op.name!r} has unknown backend {op.backend!r}")
    return result


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


def _entry_point_admits(op: ops_mod.Op, *, read_only: bool, tracker_only: bool) -> bool:
    """Whether an operation exists at all on this entry point."""
    if read_only and op.writes:
        return False
    return not (tracker_only and op.backend != "procedure")


def main(argv: list[str] | None = None, *, read_only: bool = False, tracker_only: bool = False) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if read_only:
        prog = "vetted-op-read"
        description = "Run one fixed, policy-scoped read operation. No pass-through arguments."
    elif tracker_only:
        prog = "vetted-op-tracker"
        description = (
            "Run one fixed tracker procedure (status rollup / body field). No pass-through arguments."
        )
    else:
        prog = "vetted-op"
        description = "Run one fixed, policy-scoped GitHub operation. No pass-through arguments."
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--caller", help="the skill or plugin invoking this operation")
    parser.add_argument("--config", type=Path, default=None, help="path to the policy TOML")
    parser.add_argument("--dry-run", action="store_true", help="print the argv that would run, then exit")
    parser.add_argument("operation", nargs="?", help="operation name, or 'list-ops' / 'policy'")
    parser.add_argument("params", nargs="*", help="operation parameters, positionally")
    args = parser.parse_args(argv)

    if args.operation in (None, "list-ops"):
        for name, op in sorted(ops_mod.OPS.items()):
            if not _entry_point_admits(op, read_only=read_only, tracker_only=tracker_only):
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
        # The same shape for the tracker entry point: it runs outside the
        # sandbox, so everything but the tracker procedures — whose runner
        # refuses any gh call outside repos/<tracker>/ — does not exist here,
        # whatever the policy or --caller say.
        if tracker_only and op.backend != "procedure":
            raise ops_mod.ParamError(
                f"{op.name!r} is not a tracker procedure, and this is the tracker dispatcher; "
                f"run it through 'vetted-op' or 'vetted-op-read'"
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

    if op.backend == "procedure":
        if not isinstance(command, procedures.Plan):
            raise ops_mod.ParamError(f"operation {op.name!r} produced a malformed procedure plan")
        return _run_procedure(op, command, body, dry_run=args.dry_run)

    if args.dry_run:
        if op.backend == "gh":
            if not isinstance(command, list):
                raise ops_mod.ParamError(f"operation {op.name!r} produced invalid command type")
            print(" ".join(command))
        else:
            if not isinstance(command, dict):
                raise ops_mod.ParamError(f"operation {op.name!r} produced invalid request descriptor")
            print(f"{command.get('method', 'GET')} {command.get('url')}")
            if command.get("body"):
                print("Body:", command["body"])
        return EXIT_OK

    if op.backend == "gh":
        if not isinstance(command, list):
            raise ops_mod.ParamError(f"operation {op.name!r} produced invalid command type")
        # No shell. The argv list is passed through verbatim, and any body travels
        # on stdin as bytes we already read — `gh` opens no file of ours.
        completed = subprocess.run(command, check=False, input=body)
        if completed.returncode != EXIT_OK:
            print(f"vetted-op: {op.name} failed (gh exit {completed.returncode})", file=sys.stderr)
            return EXIT_COMMAND
        return EXIT_OK
    elif op.backend == "http-read":
        if not isinstance(command, dict):
            raise ops_mod.ParamError(f"operation {op.name!r} produced invalid request descriptor")
        return _run_http(command, body=body)
    else:  # pragma: no cover
        raise ops_mod.ParamError(f"unknown backend {op.backend!r}")


def _run_procedure(op: ops_mod.Op, plan: procedures.Plan, body: bytes | None, *, dry_run: bool) -> int:
    """
    Execute a procedure plan through the tracker-only runner.

    In a dry run the reads still execute — which rollup comment to patch, or
    whether a field changes at all, depends on them — and every write is printed
    instead of run. Bodies are reported by size, never echoed, so a dry run does
    not bring the rollup or the issue body into the caller's context either.
    """
    runner = procedures.Runner(plan.tracker, allow_writes=op.writes, dry_run=dry_run)
    if dry_run:
        print(f"dry-run: {plan.describe()}")
    try:
        return plan.execute(runner, body)
    except procedures.ProcedureRefused as exc:
        print(f"vetted-op: refused: {exc}", file=sys.stderr)
        return EXIT_POLICY
    except procedures.RunnerRefused as exc:
        print(f"vetted-op: refused: {op.name} attempted a call outside its bounds: {exc}", file=sys.stderr)
        return EXIT_POLICY
    except procedures.CommandFailed as exc:
        sys.stderr.write(exc.stderr)
        print(f"vetted-op: {op.name} failed (gh exit {exc.returncode})", file=sys.stderr)
        return EXIT_COMMAND
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        # Malformed gh output (JSON the procedure did not expect).
        print(f"vetted-op: {op.name} failed: unexpected gh output ({exc})", file=sys.stderr)
        return EXIT_COMMAND


def _run_http(request_desc: dict[str, object], *, body: bytes | None) -> int:
    """Execute an HTTP read operation."""
    url = request_desc.get("url")
    method = request_desc.get("method", "GET")
    headers = request_desc.get("headers", {})
    if not isinstance(headers, dict):
        print("vetted-op: internal error: http headers must be a dict", file=sys.stderr)
        return EXIT_COMMAND

    if not isinstance(url, str) or not url.startswith("https://"):
        print("vetted-op: internal error: http request missing valid https:// url", file=sys.stderr)
        return EXIT_COMMAND

    # Optional request body from the descriptor
    desc_body = request_desc.get("body")
    payload: bytes | None = None
    if desc_body is not None:
        payload = desc_body.encode("utf-8") if isinstance(desc_body, str) else desc_body  # type: ignore[assignment]
    elif body is not None:
        payload = body

    req = urllib.request.Request(url, data=payload, method=str(method))
    if "User-Agent" not in headers:
        req.add_header("User-Agent", "apache-magpie-vetted-ops/0.1.0")
    for k, v in headers.items():
        req.add_header(str(k), str(v))

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = response.read()
            sys.stdout.buffer.write(result)
            sys.stdout.buffer.flush()
            return EXIT_OK
    except urllib.error.HTTPError as exc:
        print(f"vetted-op: http request failed with {exc.code} {exc.reason}", file=sys.stderr)
        return EXIT_COMMAND
    except urllib.error.URLError as exc:
        print(f"vetted-op: http request failed: {exc.reason}", file=sys.stderr)
        return EXIT_COMMAND
    except TimeoutError as exc:
        print(f"vetted-op: http request timed out: {exc}", file=sys.stderr)
        return EXIT_COMMAND


def main_read(argv: list[str] | None = None) -> int:
    """The `vetted-op-read` console script: `main`, with writes made unreachable."""
    return main(argv, read_only=True)


def main_tracker(argv: list[str] | None = None) -> int:
    """
    The `vetted-op-tracker` console script: `main`, with everything but the
    tracker procedures made unreachable.

    It exists so the rollup and body-field writes can run outside the sandbox
    (where `gh` can verify TLS) without excluding `vetted-op`, which would run
    the whole write catalogue there. Its writes still keep the harness's
    confirmation — it belongs in `ask`, never in `allow`.
    """
    return main(argv, tracker_only=True)
