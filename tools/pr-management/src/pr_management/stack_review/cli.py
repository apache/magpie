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
"""`pr-management stack-review …` — the deterministic half of pr-management-stack-review.

The git-backed detectors keep their own entry points and run on the local
clone: `python -m pr_management.stack_review.stack_chain` and
`python -m pr_management.stack_review.stack_ledger`.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Any

from .. import config as core_config
from . import findings, post, resolve

FAMILY = "stack-review"

#: Generated output, locks, manifests and release notes: where a retired
#: token's digits mean something else (detectors.md § Residue check).
RESIDUE_EXCLUDES = (
    "**/*.lock",
    "**/*.svg",
    "**/generated/**",
    "**/*.json",
    "**/*.yaml",
    "**/*.yml",
    "**/pyproject.toml",
    "**/newsfragments/**",
    "**/CHANGELOG*",
    "**/changelog.*",
    "**/RELEASE_NOTES*",
)
_PREFIX = re.compile(r"^magpie-stack/[0-9]{1,10}$")


def _json(path: str | None) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def _repo(args: argparse.Namespace) -> str:
    if args.repo:
        return str(args.repo)
    cfg = core_config.load(args.project_root, args.config_dir)
    if not cfg.upstream_repo:
        raise SystemExit("pr-management: no upstream_repo in project.md; pass --repo")
    return cfg.upstream_repo


def add_parsers(sub: Any) -> None:
    family = sub.add_parser(FAMILY, help="pr-management-stack-review")
    fsub = family.add_subparsers(dest="command", required=True)

    res = fsub.add_parser("resolve", help="Step 1: resolve the stack, decide the gate, render the headline")
    res.add_argument("--saved-dir", type=Path, required=True)
    res.add_argument("--viewer", required=True)
    who = res.add_mutually_exclusive_group(required=True)
    who.add_argument("--pr", type=int)
    who.add_argument("--stack", type=int)
    res.add_argument("--read-error-file", default=None, help="stderr of a failed stack read, if any")
    res.add_argument("--clone", default="<clone>", help="the local clone, for the printed git commands")
    res.add_argument("--repo", default=None)

    findings_parser = fsub.add_parser(
        "findings", help="Step 3: the detector output mapped to findings and candidates"
    )
    for name in ("chain", "seams", "floors", "ledger"):
        findings_parser.add_argument(f"--{name}", default=None)
    findings_parser.add_argument("--no-fetch", action="store_true")

    ver = fsub.add_parser("verdict", help="Step 5: the verdict from the confirmed findings")
    ver.add_argument("--findings", required=True, help="JSON list of confirmed findings")
    ver.add_argument("--ledger", default=None)
    ver.add_argument("--no-fetch", action="store_true")

    pst = fsub.add_parser(
        "post", help="Step 6: target, update-or-post, foreign markers, pointers, heads check"
    )
    pst.add_argument("--saved-dir", type=Path, required=True)
    pst.add_argument("--viewer", required=True)
    pst.add_argument("--resolved", required=True, help="the Step 1 `resolve` output, saved")
    pst.add_argument("--recheck", default=None, help="a fresh `gql-stack-of-pr` save, for the heads check")
    pst.add_argument("--body-file", required=True)
    pst.add_argument("--dry-run", action="store_true")
    pst.add_argument("--repo", default=None)

    rsd = fsub.add_parser("residue-command", help="the residue git grep, assembled and quoted")
    rsd.add_argument("--clone", required=True)
    rsd.add_argument("--prefix", required=True, help="magpie-stack/<S>")
    rsd.add_argument("--size", type=int, required=True)
    rsd.add_argument(
        "--variant", action="append", required=True, help="one spelling of a retired token (regex)"
    )
    rsd.add_argument("--exclude-glob", action="append", default=[], help="an extra glob to exclude")


def residue_command(clone: str, prefix: str, size: int, variants: list[str], extra: list[str]) -> str:
    if not _PREFIX.match(prefix):
        raise SystemExit(f"pr-management: --prefix must be magpie-stack/<number>, got {prefix!r}")
    for variant in variants:
        re.compile(variant)
    pattern = "|".join(f"(?:{v})" for v in variants)
    excludes = [f":(glob,exclude){g}" for g in (*RESIDUE_EXCLUDES, *extra)]
    return shlex.join(
        [
            "git",
            "-C",
            clone,
            "grep",
            "-n",
            "-I",
            "-i",
            "-E",
            pattern,
            f"refs/{prefix}/{size}",
            "--",
            ".",
            *excludes,
        ]
    )


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "resolve":
        cfg = core_config.load(args.project_root, args.config_dir)
        error = Path(args.read_error_file).read_text(encoding="utf-8") if args.read_error_file else None
        out = resolve.resolve(
            saved=args.saved_dir,
            cfg=cfg,
            viewer=args.viewer,
            repo=_repo(args),
            pr=args.pr,
            stack_number=args.stack,
            read_error=error,
            clone=args.clone,
        ).as_dict()
        out["docs"] = (
            ["classifications/gate.md"] if out["action"] == "review" else ["classifications/stop.md"]
        )
        return out
    if args.command == "findings":
        return findings.collect(
            _json(args.chain),
            _json(args.seams),
            _json(args.floors),
            _json(args.ledger),
            no_fetch=args.no_fetch,
        )
    if args.command == "verdict":
        confirmed = _json(args.findings)
        if isinstance(confirmed, dict):
            confirmed = confirmed.get("findings") or []
        return findings.verdict(confirmed, no_fetch=args.no_fetch, ledger=_json(args.ledger))
    if args.command == "post":
        resolved = _json(args.resolved)
        stack = int(resolved["stack"]["number"])
        repo = _repo(args)
        target = int(resolved["lowest_open_pr"])
        saved: Path = args.saved_dir
        permission_file = saved / f"permission-{args.viewer}"
        permission = (
            permission_file.read_text(encoding="utf-8").strip().strip('"')
            if permission_file.is_file()
            else None
        )
        current = None
        if args.recheck:
            data = (_json(args.recheck).get("data") or {}).get("repository") or {}
            entries = (((data.get("pullRequest") or {}).get("stack") or {}).get("entries") or {}).get(
                "nodes"
            ) or []
            current = {
                str(n["position"]): str((n.get("pullRequest") or {}).get("headRefOid") or "")
                for n in entries
                if n and (n.get("pullRequest") or {}).get("state") == "OPEN"
            }
        needs = []
        target_path = saved / f"comments-{target}.json"
        if not target_path.is_file():
            needs.append({"op": "pr-comments", "params": [str(target)], "save": target_path.name})
        merged_prs = [layer["pr"] for layer in resolved.get("layers") or [] if layer.get("state") == "merged"]
        merged: dict[int, list[dict[str, Any]]] = {}
        for pr in merged_prs:
            path = saved / f"comments-{pr}.json"
            if path.is_file():
                merged[int(pr)] = post.load_comments(path)
            else:
                needs.append({"op": "pr-comments", "params": [str(pr)], "save": path.name})
        if not permission_file.is_file():
            needs.append({"op": "upstream-permission", "params": [args.viewer], "save": permission_file.name})
        if args.recheck is None:
            needs.append(
                {
                    "op": "gql-stack-of-pr",
                    "params": [str(resolved["member_pr"])],
                    "save": f"stack-{resolved['member_pr']}-now.json",
                    "flag": "--recheck",
                }
            )
        if needs:
            return {"needs": needs}
        out = post.decide(
            repo=repo,
            viewer=args.viewer,
            stack=stack,
            target_pr=target,
            permission=permission,
            snapshot={str(k): str(v) for k, v in (resolved.get("snapshot") or {}).items()},
            current_heads=current,
            target_comments=post.load_comments(target_path),
            merged_layer_comments=merged,
            body_file=args.body_file,
            dry_run=args.dry_run,
        )
        out["marker"] = post.marker(stack, str(resolved["heads_digest"]))
        out["docs"] = ["classifications/post.md"]
        return out
    if args.command == "residue-command":
        return {
            "command": residue_command(args.clone, args.prefix, args.size, args.variant, args.exclude_glob)
        }
    raise SystemExit(f"pr-management: unknown stack-review command {args.command!r}")
