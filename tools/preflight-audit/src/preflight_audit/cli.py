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
"""CLI front-end for the pre-flight classifier dry-run.

Two modes:

- **Live**: ``preflight-audit classify --repo o/r --issues 1,2,3``
  shells out to `gh api graphql` and prints the classification.
- **Replay**: ``preflight-audit classify --load response.json``
  reads a pre-fetched GraphQL response and classifies it. Useful
  for CI eval fixtures and deterministic regression tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from preflight_audit.classifier import (
    Classification,
    Decision,
    classify_response,
)
from preflight_audit.fetch import fetch_state

# Each subagent transcript on bulk dispatch is ~50 KB; this is the
# unit the recap reports savings in.
_SUBAGENT_KB = 50


def _parse_issue_list(s: str) -> list[int]:
    out = []
    for token in s.split(","):
        token = token.strip().lstrip("#")
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError as exc:
            raise SystemExit(f"error: invalid issue number: {token!r}") from exc
    if not out:
        raise SystemExit("error: --issues parsed to empty list")
    return out


def _format_human(items: list[Classification]) -> str:
    """Group-by-decision table — same shape as the original dry-run."""
    by_decision: dict[Decision, list[Classification]] = {}
    for c in items:
        by_decision.setdefault(c.decision, []).append(c)

    lines: list[str] = []
    total = len(items) or 1
    lines.append(f"Total trackers: {total}")
    for d in (Decision.DISPATCH, Decision.DISPATCH_URGENT, Decision.SKIP_NOOP):
        n = len(by_decision.get(d, []))
        lines.append(f"  {d.value}: {n} ({100 * n // total}%)")
    lines.append("")

    for d in (Decision.SKIP_NOOP, Decision.DISPATCH_URGENT, Decision.DISPATCH):
        group = sorted(by_decision.get(d, []), key=lambda c: c.issue.number)
        if not group:
            continue
        lines.append(f"--- {d.value} ({len(group)}) ---")
        for c in group:
            labels = "+".join(sorted(c.issue.labels))[:60]
            tag = " [skill]" if c.last_is_skill_or_bot else ""
            last_by = c.issue.last_comment_author or "-"
            lines.append(f"  #{c.issue.number:>4} {c.issue.state:<6} last={last_by:<16}{tag}  → {c.reason}")
            lines.append(f"          labels: {labels}")
        lines.append("")

    skipped = len(by_decision.get(Decision.SKIP_NOOP, []))
    saved_kb = skipped * _SUBAGENT_KB
    lines.append("=== Estimated savings ===")
    lines.append(
        f"Subagents skipped: {skipped}  "
        f"→ ~{saved_kb} KB context saved "
        f"(~{saved_kb * 250} tokens @ 250 tok/KB)"
    )
    return "\n".join(lines)


def _format_json(items: list[Classification]) -> str:
    return json.dumps(
        [
            {
                "number": c.issue.number,
                "decision": c.decision.value,
                "reason": c.reason,
                "last_is_skill_or_bot": c.last_is_skill_or_bot,
                "labels": sorted(c.issue.labels),
            }
            for c in sorted(items, key=lambda c: c.issue.number)
        ],
        indent=2,
    )


def _cmd_classify(args: argparse.Namespace) -> int:
    if args.load:
        response = json.loads(Path(args.load).read_text(encoding="utf-8"))
    else:
        if not args.repo or not args.issues:
            sys.stderr.write("error: --repo and --issues are required (or use --load)\n")
            return 2
        owner, _, name = args.repo.partition("/")
        if not name:
            sys.stderr.write(f"error: --repo must be owner/name, got {args.repo!r}\n")
            return 2
        numbers = _parse_issue_list(args.issues)
        response = fetch_state(owner=owner, name=name, numbers=numbers)

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(UTC)
    extra_bots = frozenset(b.strip() for b in (args.bot_logins or "").split(",") if b.strip())
    items = classify_response(response, now=now, extra_bot_logins=extra_bots)

    if args.json:
        sys.stdout.write(_format_json(items))
    else:
        sys.stdout.write(_format_human(items))
    sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="preflight-audit",
        description=(
            "Dry-run the bulk-mode pre-flight classifier against a real "
            "or replayed tracker. Use to measure skip-rate before / after "
            "any rule change."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_cls = sub.add_parser("classify", help="classify trackers (live fetch or replay)")
    p_cls.add_argument("--repo", help="owner/name (live mode)")
    p_cls.add_argument("--issues", help="comma-separated issue numbers (live mode)")
    p_cls.add_argument(
        "--load",
        help="path to a pre-fetched GraphQL response JSON (replay mode)",
    )
    p_cls.add_argument(
        "--now",
        help="ISO-8601 timestamp to use as 'now' (deterministic replay; default: real time)",
    )
    p_cls.add_argument(
        "--bot-logins",
        help="comma-separated extra logins to treat as bot-equivalent",
    )
    p_cls.add_argument("--json", action="store_true", help="emit JSON instead of human-readable table")
    p_cls.set_defaults(func=_cmd_classify)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
