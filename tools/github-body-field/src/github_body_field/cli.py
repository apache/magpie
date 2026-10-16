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
"""CLI front-end for the body-field parser.

Operates on GitHub issue bodies via the ``gh`` CLI. The whole point
of the tool is that the body never crosses the agent boundary on a
``set`` — the read, parse, replace, and write all happen in this
subprocess, and the agent only sees the diff summary on stdout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from github_body_field.parser import (
    AmbiguousFieldError,
    FieldNotFoundError,
    extract_field,
    list_fields,
    normalise,
    replace_field,
)


def _gh_get_body(issue: str, repo: str | None) -> str:
    # The body travels as JSON: a CR is escaped there, so text-mode newline
    # translation cannot turn CRLF into LF before the parser sees it.
    cmd = ["gh", "issue", "view", issue, "--json", "body"]
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return str(json.loads(result.stdout).get("body") or "")


def _read_exact(path: str) -> str:
    """A local file's text with its line endings exactly as stored."""
    return Path(path).read_bytes().decode("utf-8")


def _gh_set_body(issue: str, repo: str | None, body: str) -> None:
    # `gh issue edit --body-file -` reads from stdin and avoids the
    # tmpfile dance plus any shell-quoting hazards.
    cmd = ["gh", "issue", "edit", issue, "--body-file", "-"]
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, input=body, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)


def _read_value(args: argparse.Namespace) -> str:
    if args.value is not None and args.value_file is not None:
        sys.stderr.write("error: pass either --value or --value-file, not both\n")
        raise SystemExit(2)
    if args.value is not None:
        return args.value
    if args.value_file is not None:
        if args.value_file == "-":
            return sys.stdin.read()
        return _read_exact(args.value_file)
    sys.stderr.write("error: one of --value / --value-file is required\n")
    raise SystemExit(2)


def _cmd_get(args: argparse.Namespace) -> int:
    body = _gh_get_body(args.issue, args.repo)
    try:
        value = extract_field(body, args.field)
    except AmbiguousFieldError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except FieldNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 3
    sys.stdout.write(value)
    if not value.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    body = _gh_get_body(args.issue, args.repo)
    names = list_fields(body)
    if args.json:
        sys.stdout.write(json.dumps(names, indent=2))
        sys.stdout.write("\n")
    else:
        for name in names:
            sys.stdout.write(f"{name}\n")
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    new_value = _read_value(args)
    body = _gh_get_body(args.issue, args.repo)
    try:
        new_body = replace_field(body, args.field, new_value)
    except AmbiguousFieldError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except FieldNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 3

    if new_body == body:
        sys.stderr.write(f"unchanged: {args.field!r} already matches new value\n")
        return 0

    # Compact diff summary on stderr so an orchestrator can log what
    # changed without us streaming the body itself.
    try:
        old_value = extract_field(body, args.field)
    except FieldNotFoundError:
        # Should not happen — we just rewrote this exact field — but
        # don't crash the apply if the post-rewrite re-parse drifts.
        old_value = "<unknown>"
    sys.stderr.write(f"field={args.field!r} old_len={len(old_value)} new_len={len(new_value)}\n")

    if args.dry_run:
        sys.stderr.write("dry-run: not pushing\n")
        return 0

    _gh_set_body(args.issue, args.repo, new_body)
    return 0


def _read_known_fields(path: str | None) -> list[str] | None:
    if path is None:
        return None
    names = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        sys.stderr.write("error: --fields-json must hold a JSON array of field names\n")
        raise SystemExit(2)
    return names


def _read_keep(items: Sequence[str]) -> dict[str, int]:
    keep: dict[str, int] = {}
    for item in items:
        name, _, line = item.rpartition("=")
        if not name or not line.isdigit():
            sys.stderr.write(f"error: --keep expects FIELD=LINE, got {item!r}\n")
            raise SystemExit(2)
        keep[name] = int(line)
    return keep


def _cmd_normalise(args: argparse.Namespace) -> int:
    if (args.issue is None) == (args.body_file is None):
        sys.stderr.write("error: pass exactly one of <issue> or --body-file\n")
        return 2
    body = _read_exact(args.body_file) if args.body_file is not None else _gh_get_body(args.issue, args.repo)
    result = normalise(body, _read_known_fields(args.fields_json), _read_keep(args.keep))
    report: dict[str, object] = {**result.as_dict(), "changed": result.text != body}
    if args.output is not None:
        Path(args.output).write_bytes(result.text.encode("utf-8"))
        report["output"] = args.output
    sys.stdout.write(json.dumps(report, indent=2))
    sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="body-field",
        description=(
            "Read or rewrite a single `### Field` section of a GitHub "
            "issue body without bringing the body into agent context."
        ),
    )
    parser.add_argument(
        "--repo",
        help="owner/repo. Defaults to the repository of the current working directory.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_get = sub.add_parser("get", help="print one field's value to stdout")
    p_get.add_argument("issue", help="issue number")
    p_get.add_argument("--field", required=True, help="exact heading text (without `### `)")
    p_get.set_defaults(func=_cmd_get)

    p_set = sub.add_parser("set", help="rewrite one field's value in place")
    p_set.add_argument("issue", help="issue number")
    p_set.add_argument("--field", required=True, help="exact heading text (without `### `)")
    p_set.add_argument("--value", help="new value (use --value-file for multi-line / shell-unsafe text)")
    p_set.add_argument(
        "--value-file",
        help="path to a file containing the new value; pass '-' to read stdin",
    )
    p_set.add_argument(
        "--dry-run",
        action="store_true",
        help="print the diff summary to stderr but skip the push",
    )
    p_set.set_defaults(func=_cmd_set)

    p_list = sub.add_parser("list", help="print every field heading present in the body")
    p_list.add_argument("issue", help="issue number")
    p_list.add_argument("--json", action="store_true", help="emit a JSON array instead of one name per line")
    p_list.set_defaults(func=_cmd_list)

    p_norm = sub.add_parser(
        "normalise",
        help="report (and optionally write locally) the canonical form of a body; never pushes",
    )
    p_norm.add_argument("issue", nargs="?", help="issue number (or pass --body-file)")
    p_norm.add_argument("--body-file", help="read the body from this local file instead of the issue")
    p_norm.add_argument("--fields-json", help="path to a JSON array of the template's field names")
    p_norm.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="FIELD=LINE",
        help="resolve a duplicate field by keeping the copy whose heading is on LINE (repeatable)",
    )
    p_norm.add_argument("--output", help="write the normalised body to this local file")
    p_norm.set_defaults(func=_cmd_normalise)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
