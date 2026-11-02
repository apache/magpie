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
"""`pr-management pre-first-pr …` — the checklist's deterministic categories and the report."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .. import config as core_config
from . import checks, report

FAMILY = "pre-first-pr"
CATEGORY_DOCS = {
    "spdx_headers": "classifications/category-a-spdx.md",
    "commit_shape": "classifications/category-b-commit-shape.md",
    "placeholder_convention": "classifications/category-c-placeholders.md",
    "contributing_conventions": "classifications/category-d-contributing.md",
    "injection_guard": "classifications/category-e-injection.md",
}
CATEGORY_DOCS = {
    "spdx_headers": "classifications/category-a-spdx.md",
    "commit_shape": "classifications/category-b-commit-shape.md",
    "placeholder_convention": "classifications/category-c-placeholders.md",
    "contributing_conventions": "classifications/category-d-contributing.md",
    "injection_guard": "classifications/category-e-injection.md",
}
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@{}~^-]{0,200}$")


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(FAMILY, help="pre-first-pr-check")
    cmd = parser.add_subparsers(dest="command", required=True)
    chk = cmd.add_parser("check", help="Steps 1-2: read the branch, run categories A-D")
    chk.add_argument("--repo-dir", type=Path, default=Path.cwd(), help="the contributor's checkout")
    chk.add_argument("--base", default=None, help="the ref to diff against (default: merge base with origin)")
    chk.add_argument("--path", default=None, help="restrict to files matching this pathspec")
    chk.add_argument("--out", type=Path, default=None, help="also write the result here, for `report`")
    rep = cmd.add_parser("report", help="Step 3: merge the agent's judgement and render the report")
    rep.add_argument("--check", type=Path, required=True, help="the `check --out` file")
    rep.add_argument("--judgement", type=Path, default=None, help="B1 / B3 / D / E findings as JSON")


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "check":
        if args.base is not None and not _REF.match(args.base):
            return {"error": f"base {args.base!r} is not a git ref"}
        default_branch = core_config.load(args.repo_dir, args.config_dir).default_branch
        try:
            result = checks.run(
                args.repo_dir, base=args.base, default_branch=default_branch, path_glob=args.path
            )
        except RuntimeError as exc:
            return {"error": str(exc)}
        if args.out is not None:
            args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
            result = {**result, "saved": str(args.out)}
        return result
    if args.command == "report":
        data = json.loads(args.check.read_text(encoding="utf-8"))
        if data.get("nothing_to_check"):
            return {
                "report": data["message"] + "\n",
                "readiness": {"signal": "ready", "blocking": 0, "advisory": 0},
                "docs": ["classifications/nothing-to-check.md"],
            }
        judgement = json.loads(args.judgement.read_text(encoding="utf-8")) if args.judgement else {}
        merged = report.merge(data["categories"], judgement)
        ready = report.readiness(merged)
        docs = [CATEGORY_DOCS[k] for k, v in merged.items() if v["status"] != "pass" and k in CATEGORY_DOCS]
        return {
            "report": report.render(data["summary"], merged),
            "readiness": ready,
            "categories": {k: v["status"] for k, v in merged.items()},
            "docs": [*docs, f"classifications/readiness-{ready['signal']}.md"],
        }
    raise SystemExit(f"pr-management pre-first-pr: unknown command {args.command!r}")
