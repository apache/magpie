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

"""Whether this branch grew a skill or an agent-instruction file past its budget.

A skill's body is paid on every invocation, its frontmatter in every session,
and an `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` in every session too.  Each has
a budget (`optimize-skill` and `optimize-agents-md`, *What counts as small
enough*), and the cheapest moment to keep a file under it is the change that
pushes it over.  So this check looks only at files the current branch changed
against its base, and reports one only when the change made it bigger and it
ends up over budget: a branch that shrinks a big file, or touches it without
growing it, is left alone.

The measurement is the one `optimize-skill/scripts/measure_skill.py` makes
(characters / 4, the pre-flight block left out of a body), so the numbers the
finding reports are the numbers the optimizer starts from.

Shown once per content: `acknowledged.oversize["<path>"]` equal to the file's
current digest means this version was already put to the user.

Every git call is read-only and runs with the repository's fsmonitor and
external diff drivers switched off, since a checkout's own config could
otherwise run code on every pre-flight.  Any git failure, or a tree that is not
a git checkout, reports nothing.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path, PurePosixPath

from .core import Finding, _merged_personal_map

CHARS_PER_TOKEN = 4
SKILL_BODY_BUDGET = 5000
SKILL_ALWAYS_ON_BUDGET = 200
INSTRUCTION_CHARS_BUDGET = 40000
INSTRUCTION_FILES = frozenset({"AGENTS.md", "CLAUDE.md", "GEMINI.md"})
#: Trees that are not the project's own source: the framework snapshot is
#: changed only by `setup update`, and vendored packages are not ours to trim.
SKIPPED_PARTS = frozenset({".apache-magpie", "node_modules"})
#: The base a branch is measured against, first that resolves wins: the
#: canonical repository when a fork is `origin`, then `origin`, then local.
BASE_REFS = (
    "upstream/HEAD",
    "upstream/main",
    "upstream/master",
    "origin/HEAD",
    "origin/main",
    "origin/master",
    "main",
    "master",
)
_GIT_SAFE = ("-c", "core.fsmonitor=false", "-c", "core.quotePath=false")

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
_PREFLIGHT = re.compile(r"<!-- BEGIN MAGPIE PREFLIGHT.*?<!-- END MAGPIE PREFLIGHT -->\n?", re.S)


def _git(root: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *_GIT_SAFE, *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _scalar(frontmatter: str, key: str) -> str:
    """One frontmatter value, plain or block (`key: |` / `key: >-`)."""
    m = re.search(rf"^{key}:[ \t]*(\|[-+]?|>[-+]?)?[ \t]*(.*)$", frontmatter, re.M)
    if not m:
        return ""
    if not m.group(1):
        return m.group(2).strip().strip("'\"")
    body: list[str] = []
    for line in frontmatter[m.end() :].split("\n")[1:]:
        if line.strip() and not line[:1].isspace():
            break
        body.append(line)
    return "\n".join(body).strip()


def measure_skill(text: str) -> tuple[int, int]:
    """(body tokens, always-on tokens) for a `SKILL.md`'s text."""
    m = _FRONTMATTER.match(text)
    if not m:
        return len(text) // CHARS_PER_TOKEN, 0
    fm = m.group(1)
    always_on = len(_scalar(fm, "name")) + 2 + len(_scalar(fm, "description"))
    when_to_use = _scalar(fm, "when_to_use")
    if when_to_use:
        always_on += 3 + len(when_to_use)
    body = _PREFLIGHT.sub("", text[m.end() :])
    return len(body) // CHARS_PER_TOKEN, always_on // CHARS_PER_TOKEN


def _kind(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if SKIPPED_PARTS.intersection(parts):
        return None
    if parts[-1] == "SKILL.md":
        return "skill"
    if parts[-1] in INSTRUCTION_FILES:
        return "instructions"
    return None


def _base(root: Path) -> str | None:
    for ref in BASE_REFS:
        if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") is None:
            continue
        merge_base = _git(root, "merge-base", "HEAD", ref)
        if merge_base:
            return merge_base.strip()
    return None


def _changed(root: Path, base: str) -> list[str]:
    tracked = _git(root, "diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", base) or ""
    untracked = _git(root, "ls-files", "-z", "--others", "--exclude-standard") or ""
    names = {n for n in (tracked + untracked).split("\0") if n}
    return sorted(n for n in names if _kind(n))


def _measure(kind: str, text: str) -> dict[str, int]:
    if kind == "skill":
        body, always_on = measure_skill(text)
        return {"body_tokens": body, "always_on_tokens": always_on}
    return {"chars": len(text)}


def _over(kind: str, now: dict[str, int], before: dict[str, int]) -> list[str]:
    """Each budget the change grew the file past or further past."""
    budgets = (
        {"body_tokens": SKILL_BODY_BUDGET, "always_on_tokens": SKILL_ALWAYS_ON_BUDGET}
        if kind == "skill"
        else {"chars": INSTRUCTION_CHARS_BUDGET}
    )
    return [key for key, cap in budgets.items() if now[key] > cap and now[key] > before.get(key, 0)]


def oversized(
    root: Path, base: str | None = None, acknowledged: dict[str, str] | None = None
) -> list[dict[str, object]]:
    """Every changed file the branch grew past a budget, against `base` (default: the merge-base)."""
    if _git(root, "rev-parse", "--is-inside-work-tree") is None:
        return []
    if base is None:
        base = _base(root)
    else:
        base = (_git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}") or "").strip() or None
    if base is None:
        return []
    top = (_git(root, "rev-parse", "--show-toplevel") or "").strip()
    if not top:
        return []
    files: list[dict[str, object]] = []
    for name in _changed(root, base):
        path = Path(top) / name
        if path.is_symlink() or not path.is_file():
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        digest = hashlib.sha256(raw).hexdigest()[:16]
        if acknowledged and acknowledged.get(name) == digest:
            continue
        kind = _kind(name)
        assert kind is not None
        now = _measure(kind, raw.decode("utf-8", errors="replace"))
        old = _git(root, "show", f"{base}:{name}")
        before = _measure(kind, old) if old is not None else {}
        over = _over(kind, now, before)
        if over:
            files.append(
                {
                    "path": name,
                    "kind": kind,
                    "over": over,
                    "now": now,
                    "base": before,
                    "digest": digest,
                    "optimizer": "optimize-skill" if kind == "skill" else "optimize-agents-md",
                }
            )
    return files


def findings(root: Path) -> list[Finding]:
    """One `oversize` finding listing every changed file this branch grew past a budget."""
    files = oversized(root, acknowledged=_merged_personal_map(root, "acknowledged", "oversize"))
    if not files:
        return []
    return [Finding("end-of-run", "oversize", "oversize", {"files": files})]


_LABELS = {
    "body_tokens": ("body", "tokens", SKILL_BODY_BUDGET),
    "always_on_tokens": ("name + description + when_to_use", "tokens", SKILL_ALWAYS_ON_BUDGET),
    "chars": ("file", "characters", INSTRUCTION_CHARS_BUDGET),
}


def markdown(files: list[dict[str, object]]) -> str:
    """The report CI writes to the job summary."""
    lines = [
        "| File | Over | Before | After | Budget | Optimize with |",
        "|---|---|---|---|---|---|",
    ]
    for file in files:
        now, before = file["now"], file["base"]
        assert isinstance(now, dict) and isinstance(before, dict)
        for key in file["over"]:  # type: ignore[attr-defined]
            what, unit, cap = _LABELS[key]
            was = before.get(key)
            lines.append(
                f"| `{file['path']}` | {what} | {'new file' if was is None else f'{was:,}'} "
                f"| {now[key]:,} {unit} | {cap:,} | `{file['optimizer']}` |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """`python3 -m setup_preflight.oversize [--base REF]`: exit 1 when a changed file grew past a budget."""
    import argparse
    import json

    parser = argparse.ArgumentParser(prog="setup-preflight-oversize", description=main.__doc__)
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument(
        "--base", help="the ref to compare against (default: the merge-base with the base branch)"
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    files = oversized(args.project_root, base=args.base)
    if args.format == "markdown":
        print(
            markdown(files) if files else "No changed skill or agent-instruction file grew past its budget."
        )
    else:
        print(json.dumps(files, indent=2))
    return 1 if files else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
