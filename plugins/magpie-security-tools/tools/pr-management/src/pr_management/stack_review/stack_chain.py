#!/usr/bin/env python3
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

"""Git-backed checks over the fetched heads of a pull-request stack.

Works on refs only — ``refs/<prefix>/<position>`` for every layer and
``refs/<prefix>/trunk`` for the stack base — so the working tree is never
touched. The skill fetches those refs once (a proposed step) and deletes
them at the end.

Subcommands::

    stack_chain.py fetch-command --repo-url URL --prefix magpie-stack/120 \\
        --trunk main --pr 1=1001 --pr 2=1002 ...          # prints the git fetch line
    stack_chain.py --repo <clone> chain  --prefix magpie-stack/120 --size 4 [--from 2]  # chain currency JSON
    stack_chain.py --repo <clone> seams  --prefix magpie-stack/120 --size 4 [--from 2] [--layers 2,3]
    stack_chain.py --repo <clone> floors --prefix magpie-stack/120 --size 4 [--from 2]  # declared runtime floors per head
    stack_chain.py digest --head 2=<sha> --head 3=<sha>      # heads digest without fetched refs (no-fetch)
    stack_chain.py cleanup-command --prefix magpie-stack/120 --size 4

``--repo`` names the clone that holds the refs; without it the current
directory is used. ``--from`` is the lowest open position: merged layers
below it are neither fetched nor analysed, and the trunk is its base.

"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from collections.abc import Iterable
from typing import Any

# Definitions whose removal matters at the seam between layers. Column-0
# anchoring keeps nested helpers out; those rarely cross a layer boundary.
_REMOVED_DEF = re.compile(
    r"^-(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"  # python
    r"|^-(?:export\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"  # js/ts
    r"|^-(?:pub\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]*)"  # rust
    r"|^-func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)"  # go
    r"|^-([A-Z][A-Z0-9_]{2,})\s*(?::\s*[^=]+)?=[^=]"  # module-level CONSTANT = ...
)
_ADDED_DEF = re.compile(
    r"^\+(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"|^\+(?:export\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"
    r"|^\+(?:pub\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"|^\+func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)"
    r"|^\+([A-Z][A-Z0-9_]{2,})\s*(?::\s*[^=]+)?=[^=]"
)
# Definitions are only extracted from the languages the patterns cover: the
# CONSTANT branch would otherwise match `KEY=value` lines in shell scripts,
# Makefiles and env files.
_SOURCE_SUFFIXES = (".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".rs", ".go")
_DELETED_FILE = re.compile(r"^deleted file mode")
_DIFF_HEADER = re.compile(r"^diff --git a/(.*?) b/(.*)$")
# Names too short or too common to grep for meaningfully.
_MIN_NAME_LEN = 4
MAX_HITS_PER_NAME = 12
# Grep is restricted to text sources; lock files and generated docs echo
# every identifier and would bury the signal.
_GREP_EXCLUDES = (":!*.lock", ":!*.svg", ":!*.min.js", ":!*.md5sum", ":!*.snap")
MAX_COMMITS_PER_LAYER = 30
MAX_COMMIT_BODY_CHARS = 4000
MAX_REMOVED_NAMES = 50
# Declared runtime floors: (pathspec, line regex with one capture group).
_FLOOR_PATTERNS: tuple[tuple[str, str], ...] = (
    ("*pyproject.toml", r"^\s*requires-python\s*=\s*[\"']([^\"']+)[\"']"),
    ("*setup.cfg", r"^\s*python_requires\s*=\s*(.+?)\s*$"),
    ("*setup.py", r"python_requires\s*=\s*[\"']([^\"']+)[\"']"),
    # PEP 723 inline script metadata (`# /// script` blocks).
    ("*.py", r"^#\s*requires-python\s*=\s*[\"']([^\"']+)[\"']"),
    ("*Cargo.toml", r"^\s*rust-version\s*=\s*[\"']([^\"']+)[\"']"),
    ("*go.mod", r"^go\s+(\S+)"),
    ("*package.json", r"\"node\"\s*:\s*\"([^\"]+)\""),
)


REPO: str | None = None


def _git_base() -> list[str]:
    return ["git", "-C", REPO] if REPO else ["git"]


def _git(*args: str, ok: tuple[int, ...] = (0,)) -> str:
    # Repositories hold files in any encoding; one non-UTF-8 line must not end the run.
    result = subprocess.run(
        [*_git_base(), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in ok:
        raise SystemExit(f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def _ref(prefix: str, position: int | str) -> str:
    return f"refs/{prefix}/{position}"


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            [*_git_base(), "merge-base", "--is-ancestor", ancestor, descendant], check=False
        ).returncode
        == 0
    )


def _count(rev_range: str, *flags: str) -> int:
    out = _git("rev-list", "--count", *flags, rev_range).strip()
    return int(out) if out else 0


def fetch_command(repo_url: str, prefix: str, trunk: str, prs: dict[int, int]) -> str:
    """The single `git fetch` that brings every layer head and the trunk in as refs."""
    specs = [f"+refs/heads/{trunk}:{_ref(prefix, 'trunk')}"]
    specs.extend(
        f"+refs/pull/{number}/head:{_ref(prefix, position)}" for position, number in sorted(prs.items())
    )
    # The trunk name comes from the API and is printed as a line the agent runs.
    return shlex.join(["git", "fetch", "--no-tags", repo_url, *specs])


def cleanup_command(prefix: str, size: int) -> str:
    refs = [_ref(prefix, "trunk")] + [_ref(prefix, k) for k in range(1, size + 1)]
    return " && ".join(f"git update-ref -d {ref}" for ref in refs)


def _ref_exists(ref: str) -> bool:
    return (
        subprocess.run(
            [*_git_base(), "rev-parse", "--verify", "-q", ref], check=False, capture_output=True
        ).returncode
        == 0
    )


def heads_digest(heads: dict[int, str]) -> str:
    """First 16 hex of sha256 over ``"<k>:<sha>\\n"`` for every layer, ascending.

    The exact bytes matter: the summary comment's marker carries this value so
    a re-run can tell whether the comment describes the current heads.
    """
    payload = "".join(f"{k}:{heads[k]}\n" for k in sorted(heads))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def commit_messages(below: str, head: str) -> list[dict[str, str]]:
    """Headline and body of every commit a layer carries, newest first."""
    raw = _git("log", "--format=%H%x1f%s%x1f%b%x1e", f"{below}..{head}")
    messages = []
    for record in raw.split("\x1e"):
        if not record.strip():
            continue
        sha, _, rest = record.strip("\n").partition("\x1f")
        headline, _, body = rest.partition("\x1f")
        messages.append({"sha": sha, "headline": headline, "body": body.strip()[:MAX_COMMIT_BODY_CHARS]})
    return messages[:MAX_COMMITS_PER_LAYER]


def _positions(start: int, size: int) -> range:
    if not 1 <= start <= size:
        raise SystemExit(f"--from {start} is outside the stack (1..{size})")
    return range(start, size + 1)


def chain(prefix: str, size: int, start: int = 1) -> dict[str, Any]:
    positions = _positions(start, size)
    missing = [k for k in ["trunk", *positions] if not _ref_exists(_ref(prefix, k))]
    if missing:
        raise SystemExit(f"missing refs under refs/{prefix}/: {missing} — run the fetch command first")
    trunk = _ref(prefix, "trunk")
    bottom = _ref(prefix, start)
    merge_base = _git("merge-base", trunk, bottom).strip()
    if not merge_base:
        raise SystemExit(f"{bottom} shares no history with the trunk")
    layers: list[dict[str, Any]] = []
    for k in positions:
        # The lowest open layer is measured from its merge-base with the trunk:
        # a trunk that moved on is "behind", reported separately, not a stale
        # base. Every other layer must contain the head of the layer below.
        below = merge_base if k == start else _ref(prefix, k - 1)
        head = _ref(prefix, k)
        layers.append(
            {
                "position": k,
                "head": _git("rev-parse", head).strip(),
                "contains_below": _is_ancestor(below, head),
                "own_commits": _count(f"{below}..{head}"),
                "merge_commits": _count(f"{below}..{head}", "--merges"),
                "commit_headlines": [
                    line for line in _git("log", "--format=%s", f"{below}..{head}").splitlines() if line
                ][:MAX_COMMITS_PER_LAYER],
                "commit_messages": commit_messages(below, head),
            }
        )
    top = _ref(prefix, size)
    stack_files = set(_git("diff", "--name-only", merge_base, top).splitlines())
    trunk_files = set(_git("diff", "--name-only", merge_base, trunk).splitlines())
    return {
        "merge_base": merge_base,
        "heads_digest": heads_digest({layer["position"]: layer["head"] for layer in layers}),
        "linear": all(layer["contains_below"] and layer["merge_commits"] == 0 for layer in layers),
        "behind_trunk_commits": _count(f"{merge_base}..{trunk}"),
        "trunk_touches_stack_files": sorted(stack_files & trunk_files),
        "layers": layers,
    }


def removed_definitions(diff_text: str) -> tuple[dict[str, str], list[str]]:
    """Names defined on removed lines and not re-added in the same diff, plus deleted files."""
    removed: dict[str, str] = {}
    added: set[str] = set()
    deleted_files: list[str] = []
    current = ""
    for line in diff_text.splitlines():
        header = _DIFF_HEADER.match(line)
        if header:
            current = header.group(2)
            continue
        if _DELETED_FILE.match(line):
            deleted_files.append(current)
            continue
        if not current.endswith(_SOURCE_SUFFIXES):
            continue
        m = _REMOVED_DEF.match(line)
        if m:
            name = next(g for g in m.groups() if g)
            if len(name) >= _MIN_NAME_LEN:
                removed.setdefault(name, current)
            continue
        m = _ADDED_DEF.match(line)
        if m:
            added.add(next(g for g in m.groups() if g))
    return {name: path for name, path in removed.items() if name not in added}, deleted_files


def grep_at(ref: str, name: str, limit: int | None = MAX_HITS_PER_NAME) -> list[str]:
    """`path:line:text` hits for a whole-word, text-file grep of *name* at *ref*.

    The name is matched literally: JS identifiers may carry `$`, which a
    regex would read as an anchor. ``limit=None`` returns every hit.
    """
    out = _git("grep", "-n", "-w", "-I", "-F", "-e", name, ref, "--", ".", *_GREP_EXCLUDES, ok=(0, 1))
    # git grep prints "<ref>:<path>:<lineno>:<text>"; drop the ref.
    hits = [line.partition(":")[2] for line in out.splitlines()]
    return hits if limit is None else hits[:limit]


def _without_line_numbers(hits: Iterable[str]) -> set[str]:
    return {f"{h.split(':', 1)[0]}:{h.split(':', 2)[2]}" for h in hits if h.count(":") >= 2}


def new_on_trunk(name: str, merge_base: str, trunk: str) -> list[str]:
    """Trunk hits for *name* that did not exist at the merge-base.

    The trunk still carries every definition the stack removes, so raw trunk
    hits say nothing; a reference that appeared on the trunk after the stack
    was cut is the one that breaks the stack on its next rebase.
    """
    # Compare the full hit sets and cap only the result: capping first would
    # report the merge-base's 13th hit as new whenever the trunk drops one.
    before = _without_line_numbers(grep_at(merge_base, name, limit=None))
    new = [
        h
        for h in grep_at(trunk, name, limit=None)
        if h.count(":") >= 2 and f"{h.split(':', 1)[0]}:{h.split(':', 2)[2]}" not in before
    ]
    return new[:MAX_HITS_PER_NAME]


def module_name(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    stem = path[:-3]
    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]
    return stem.rsplit("/", 1)[-1]


def seams(prefix: str, size: int, layers: Iterable[int] | None = None, start: int = 1) -> dict[str, Any]:
    trunk = _ref(prefix, "trunk")
    open_positions = _positions(start, size)
    merge_base = _git("merge-base", trunk, _ref(prefix, start)).strip()
    positions = [k for k in layers if k in open_positions] if layers else list(open_positions)
    report: list[dict[str, Any]] = []
    for k in positions:
        below = trunk if k == start else _ref(prefix, k - 1)
        head = _ref(prefix, k)
        diff = _git("diff", f"{below}...{head}")
        removed, deleted_files = removed_definitions(diff)
        for path in deleted_files:
            mod = module_name(path)
            if mod and len(mod) >= _MIN_NAME_LEN:
                removed.setdefault(mod, path)
        names: dict[str, dict[str, Any]] = {}
        for name, path in sorted(removed.items()):
            own = grep_at(head, name)
            later = {str(j): hits for j in range(k + 1, size + 1) if (hits := grep_at(_ref(prefix, j), name))}
            trunk_hits = new_on_trunk(name, merge_base, trunk)
            if own or later or trunk_hits:
                names[name] = {
                    "removed_in": path,
                    "at_own_head": own,
                    "at_later_heads": later,
                    "new_on_trunk": trunk_hits,
                }
        report.append(
            {
                "position": k,
                "removed_definitions": len(removed),
                "removed_names": sorted(removed)[:MAX_REMOVED_NAMES],
                "hits": names,
            }
        )
    return {"merge_base": merge_base, "layers": report}


def declared_floors(ref: str) -> dict[str, str]:
    """``path -> declared floor`` for every manifest at *ref*."""
    floors: dict[str, str] = {}
    for pathspec, pattern in _FLOOR_PATTERNS:
        regex = re.compile(pattern)
        out = _git(
            "grep",
            "-n",
            "-E",
            "-I",
            pattern.replace("\\s", "[[:space:]]").split("(")[0].lstrip("^").strip(),
            ref,
            "--",
            pathspec,
            ok=(0, 1),
        )
        for line in out.splitlines():
            _, _, rest = line.partition(":")
            path, _, rest = rest.partition(":")
            _, _, text = rest.partition(":")
            m = regex.search(text)
            if m:
                floors[path] = m.group(1).strip()
    return floors


def floors(prefix: str, size: int, start: int = 1) -> dict[str, Any]:
    trunk = _ref(prefix, "trunk")
    positions = _positions(start, size)
    per_layer: dict[int, dict[str, str]] = {start - 1: declared_floors(trunk)}
    for k in positions:
        per_layer[k] = declared_floors(_ref(prefix, k))
    changes = []
    for k in positions:
        before, after = per_layer[k - 1], per_layer[k]
        moved = {p: (before[p], after[p]) for p in set(before) & set(after) if before[p] != after[p]}
        added = {p: after[p] for p in set(after) - set(before)}
        removed = {p: before[p] for p in set(before) - set(after)}
        if moved or added or removed:
            changes.append(
                {
                    "position": k,
                    "moved": {p: {"from": a, "to": b} for p, (a, b) in sorted(moved.items())},
                    "added_manifests": dict(sorted(added.items())),
                    "removed_manifests": dict(sorted(removed.items())),
                }
            )
    return {
        "trunk": per_layer[start - 1],
        "layers": [{"position": k, "floors": per_layer[k]} for k in positions],
        "floor_changes": changes,
    }


def _parse_pr(value: str) -> tuple[int, int]:
    position, sep, number = value.partition("=")
    if not sep or not position.isdigit() or not number.isdigit():
        raise argparse.ArgumentTypeError("expected <position>=<pr-number>")
    return int(position), int(number)


def _parse_head(value: str) -> tuple[int, str]:
    position, sep, sha = value.partition("=")
    if not sep or not position.isdigit() or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise argparse.ArgumentTypeError("expected <position>=<40-hex head sha>")
    return int(position), sha


def _parse_layers(value: str) -> list[int]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts or not all(part.isdigit() for part in parts):
        raise argparse.ArgumentTypeError("expected comma-separated positions, e.g. 2,3")
    return [int(part) for part in parts]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", help="clone holding the refs (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-command")
    fetch.add_argument("--repo-url", required=True)
    fetch.add_argument("--prefix", required=True)
    fetch.add_argument("--trunk", required=True)
    fetch.add_argument("--pr", action="append", required=True, type=_parse_pr, metavar="POS=NUMBER")

    digest = sub.add_parser("digest")
    digest.add_argument("--head", action="append", required=True, type=_parse_head, metavar="POS=SHA")

    for name in ("chain", "seams", "floors", "cleanup-command"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--prefix", required=True)
        cmd.add_argument("--size", required=True, type=int)
        if name != "cleanup-command":
            cmd.add_argument(
                "--from", dest="start", type=int, default=1, help="lowest open position (default 1)"
            )
        if name == "seams":
            cmd.add_argument(
                "--layers", type=_parse_layers, help="comma-separated positions to analyse (default all open)"
            )

    args = parser.parse_args(argv)
    if getattr(args, "size", 1) < 1:
        parser.error("--size must be at least 1")
    global REPO
    REPO = args.repo
    if args.command == "fetch-command":
        print(fetch_command(args.repo_url, args.prefix, args.trunk, dict(args.pr)))
    elif args.command == "digest":
        print(heads_digest(dict(args.head)))
    elif args.command == "cleanup-command":
        print(cleanup_command(args.prefix, args.size))
    elif args.command == "chain":
        json.dump(chain(args.prefix, args.size, args.start), sys.stdout, indent=1)
        print()
    elif args.command == "floors":
        json.dump(floors(args.prefix, args.size, args.start), sys.stdout, indent=1)
        print()
    else:
        json.dump(seams(args.prefix, args.size, args.layers, args.start), sys.stdout, indent=1)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
