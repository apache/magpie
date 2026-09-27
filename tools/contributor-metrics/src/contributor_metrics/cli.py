# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""contributor-metrics CLI: `fetch` from GitHub, `score` offline."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from contributor_metrics.fetch import GhError, InvalidLogin, fetch_items
from contributor_metrics.model import Item, Weights
from contributor_metrics.score import score


def _since(end: str, months: int) -> str:
    e = date.fromisoformat(end)
    y, m = divmod(e.year * 12 + e.month - 1 - months, 12)
    return date(y, m + 1, min(e.day, 28)).isoformat()


def _read(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="contributor-metrics")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="fetch a contributor's activity items from GitHub")
    f.add_argument("--repo", required=True)
    f.add_argument("--login", required=True)
    f.add_argument("--end", required=True)
    f.add_argument("--months", type=int, default=6)
    f.add_argument("--review-depth", type=int, default=10)
    f.add_argument("--phrases-file")
    f.add_argument("--maintainers-file")
    f.add_argument("--out", required=True)
    s = sub.add_parser("score", help="apply weights and the pushback penalty to fetched items")
    s.add_argument("--items", required=True)
    s.add_argument("--classes")
    s.add_argument("--weights")
    s.add_argument("--area-prefix", default="area:")
    s.add_argument("--out", required=True)
    args = p.parse_args(argv)

    if args.cmd == "fetch":
        since = _since(args.end, args.months)
        phrases = Path(args.phrases_file).read_text().splitlines() if args.phrases_file else []
        maintainers = Path(args.maintainers_file).read_text().split() if args.maintainers_file else []
        try:
            items, caps = fetch_items(
                args.repo,
                args.login,
                since=since,
                end=args.end,
                review_depth=args.review_depth,
                phrases=phrases,
                maintainers=maintainers,
            )
        except InvalidLogin as exc:
            print(f"invalid GitHub handle: {exc}", file=sys.stderr)
            return 2
        except GhError as exc:
            print(f"gh failed: {exc}", file=sys.stderr)
            return 1
        payload = {
            "login": args.login,
            "repo": args.repo,
            "since": since,
            "end": args.end,
            "caps_hit": caps,
            "items": [i.to_json() for i in items],
        }
        Path(args.out).write_text(json.dumps(payload, indent=2))
        return 0

    data = _read(args.items)
    weights, notes = Weights.from_mapping(_read(args.weights))
    result = score(
        [Item.from_json(d) for d in data["items"]],
        _read(args.classes),
        weights,
        since=data["since"],
        end=data["end"],
        area_prefix=args.area_prefix,
        caps_hit=data.get("caps_hit", []),
    )
    result["notes"] = notes + result["notes"]
    Path(args.out).write_text(json.dumps(result, indent=2))
    return 0
