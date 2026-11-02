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
"""The pre-first-PR checklist: read-only `git` over the local branch, then categories A-D.

`git` runs locally and read-only (`merge-base`, `diff`, `log`, `show`); the
working tree is never touched. What stays with the agent is listed per
category under `judgement`: B1 (imperative mood), B3 (was a commit
AI-assisted), the D subject-wording check, and E (prompt injection).
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import mdconfig
from ..layers import OVERRIDES_DIR, personal_layers

#: The placeholder set the framework declares (AGENTS.md § Placeholder convention).
PLACEHOLDERS = ("<upstream>", "<default-branch>", "<project-config>", "<tracker>", "<PROJECT>")
#: Files exempt from category C: they are templates themselves.
TEMPLATE_GLOBS = ("*/_template/*", "projects/_template/*", "*example*")
#: Files that cannot carry a comment header, so category A skips them.
NO_HEADER_SUFFIXES = (
    ".json",
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".whl",
    ".svg",
)
NO_HEADER_NAMES = ("LICENSE", "NOTICE", ".gitkeep")
#: Co-Authored-By names or addresses that attribute authorship to an AI agent.
AI_COAUTHORS = re.compile(
    r"claude|anthropic|chatgpt|openai|\bgpt|copilot|gemini|codex|cursor|devin|\bllm\b|\bai\b",
    flags=re.IGNORECASE,
)
SECRET = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})"
)
SPDX_LINES = 10
LARGE_BYTES = 1_000_000
ATTRIBUTION_FILE = "commit-attribution.toml"
CONVENTIONS = frozenset({"generated-by", "assisted-by", "co-authored-by", "none", "custom"})


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def git_bytes(repo: Path, *args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    return done.stdout if done.returncode == 0 else b""


def attribution_convention(repo: Path) -> str:
    """The commit-attribution convention, resolved per docs/setup/commit-attribution.md.

    The same order as `agent_guard.resolve_commit_attribution`: the project's
    committed choice wins unless it says `contributor-choice`; then the
    contributor's personal file; then `generated-by`. Anything unreadable or
    unknown fails closed to `generated-by`.
    """

    def read(path: Path) -> str | None:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            raise ValueError(path) from None
        value = data.get("convention")
        return value.strip().lower() if isinstance(value, str) else None

    try:
        project = read(repo / OVERRIDES_DIR / ATTRIBUTION_FILE)
        if project is not None and project != "contributor-choice":
            return project if project in CONVENTIONS else "generated-by"
        for layer in personal_layers(repo):
            local = read(layer / ATTRIBUTION_FILE)
            if local is not None:
                return local if local in CONVENTIONS else "generated-by"
    except ValueError:
        return "generated-by"
    return "generated-by"


def expected_license(repo: Path) -> str | None:
    """The SPDX identifier `project.md` declares (`license` / `spdx_license`), if any."""
    values = mdconfig.key_values(mdconfig.Resolver(repo).read("project.md"))
    for key in ("spdx_license", "spdx_license_identifier", "license"):
        value = values.get(key)
        if value and re.fullmatch(r"[A-Za-z0-9.+-]+", value):
            return value
    return None


@dataclass
class Commit:
    sha: str
    subject: str
    message: str

    def trailers(self, name: str) -> list[str]:
        return re.findall(rf"(?im)^{re.escape(name)}:\s*(.+)$", self.message)


@dataclass
class Branch:
    base: str
    files: list[tuple[str, str]]  # (status letter, path)
    commits: list[Commit]
    contents: dict[str, bytes] = field(default_factory=dict)
    added_lines: dict[str, list[str]] = field(default_factory=dict)

    @property
    def added(self) -> list[str]:
        return [p for s, p in self.files if s == "A"]


def collect(repo: Path, *, base: str | None, default_branch: str, path_glob: str | None) -> Branch:
    if base is None:
        base = git(repo, "merge-base", "HEAD", f"origin/{default_branch}").strip()
    spec = ["--", path_glob] if path_glob else []
    files: list[tuple[str, str]] = []
    for line in git(repo, "diff", "--name-status", "--no-renames", f"{base}..HEAD", *spec).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append((parts[0][:1], parts[-1]))
    commits: list[Commit] = []
    for record in git(repo, "log", f"{base}..HEAD", "--format=%H%x00%B%x1e").split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, _, message = record.partition("\x00")
        commits.append(
            Commit(sha.strip(), message.strip().splitlines()[0] if message.strip() else "", message)
        )
    branch = Branch(base=base, files=files, commits=commits)
    for status, path in files:
        if status in ("A", "M"):
            branch.contents[path] = git_bytes(repo, "show", f"HEAD:{path}")
            diff = git(repo, "diff", "-U0", f"{base}..HEAD", "--", path)
            branch.added_lines[path] = [
                line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
            ]
    return branch


def _result(
    status: str, details: str = "", locations: list[str] | None = None, **extra: Any
) -> dict[str, Any]:
    return {"status": status, "details": details, "locations": locations or [], **extra}


def check_spdx(branch: Branch, license_id: str | None) -> dict[str, Any]:
    missing: list[str] = []
    wrong: list[str] = []
    for path in branch.added:
        name = path.rsplit("/", 1)[-1]
        if path.endswith(NO_HEADER_SUFFIXES) or name in NO_HEADER_NAMES:
            continue
        data = branch.contents.get(path, b"")
        if b"\0" in data[:8000]:
            continue
        head = data.decode("utf-8", errors="replace").splitlines()[:SPDX_LINES]
        found = next(
            (
                re.search(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)", line)
                for line in head
                if "SPDX-License-Identifier" in line
            ),
            None,
        )
        if found is None:
            missing.append(path)
        elif license_id and found.group(1) != license_id:
            wrong.append(path)
    if not missing and not wrong:
        return _result("pass")
    details = []
    if missing:
        details.append(f"{len(missing)} new file(s) have no SPDX header in their first {SPDX_LINES} lines")
    if wrong:
        details.append(f"{len(wrong)} new file(s) declare a licence other than {license_id}")
    return _result("fail", "; ".join(details) + ".", missing + wrong)


def check_commits(branch: Branch, convention: str) -> dict[str, Any]:
    """B2 deterministically; B1 and B3 are listed for the agent."""
    violations: list[dict[str, Any]] = []
    for commit in branch.commits:
        if convention != "co-authored-by":
            ai = [c for c in commit.trailers("Co-Authored-By") if AI_COAUTHORS.search(c)]
            if ai:
                violations.append(
                    {
                        "commit": commit.sha[:7],
                        "subject": commit.subject,
                        "rule": "B2",
                        "summary": f"Co-Authored-By attributes an AI agent ({ai[0].strip()})",
                    }
                )
    trailer = {
        "generated-by": "Generated-by",
        "assisted-by": "Assisted-by",
        "co-authored-by": "Co-authored-by",
    }
    expected = trailer.get(convention)
    without = [c for c in branch.commits if expected and not c.trailers(expected)]
    judgement = {
        "B1": [{"commit": c.sha[:7], "subject": c.subject} for c in branch.commits],
        "B3": {
            "convention": convention,
            "trailer": expected,
            "commits_without_trailer": [{"commit": c.sha[:7], "subject": c.subject} for c in without],
        },
    }
    if violations:
        return _result(
            "fail",
            "A commit attributes authorship to an AI agent; use the convention's trailer instead.",
            [v["commit"] for v in violations],
            violations=violations,
            judgement=judgement,
        )
    return _result("pass", judgement=judgement)


def _exempt(path: str) -> bool:
    return any(fnmatch.fnmatch(path, glob) for glob in TEMPLATE_GLOBS)


def check_placeholders(branch: Branch) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for path, lines in branch.added_lines.items():
        if _exempt(path):
            continue
        for line in lines:
            for token in PLACEHOLDERS:
                if token in line:
                    hits.append({"path": path, "token": token, "line": line.strip()[:120]})
    if not hits:
        return _result("pass")
    return _result(
        "fail",
        f"{len(hits)} un-substituted placeholder occurrence(s) in non-template files.",
        sorted({h["path"] for h in hits}),
        occurrences=hits,
    )


def check_contributing(branch: Branch) -> dict[str, Any]:
    """D: binaries, credentials and large artefacts; the subject wording is the agent's."""
    problems: list[dict[str, str]] = []
    for status, path in branch.files:
        if status != "A":
            continue
        data = branch.contents.get(path, b"")
        name = path.rsplit("/", 1)[-1]
        if name == ".env" or (
            name.startswith(".env.") and not name.endswith((".example", ".sample", ".template"))
        ):
            problems.append({"path": path, "summary": "committed environment file"})
        elif b"\0" in data[:8000]:
            problems.append({"path": path, "summary": "committed binary file"})
        elif len(data) > LARGE_BYTES:
            problems.append(
                {"path": path, "summary": f"large file ({len(data) // 1024} KiB) — generated artefact?"}
            )
    for path, lines in branch.added_lines.items():
        if any(SECRET.search(line) for line in lines):
            problems.append({"path": path, "summary": "token-like string in added lines"})
    advisory = "Confirm the PR description follows the CONTRIBUTING guide's PR-body template."
    judgement = {"subjects": [{"commit": c.sha[:7], "subject": c.subject} for c in branch.commits]}
    if problems:
        return _result(
            "fail",
            "; ".join(p["summary"] for p in problems) + ".",
            [p["path"] for p in problems],
            problems=problems,
            advisory=advisory,
            judgement=judgement,
        )
    return _result("pass", advisory=advisory, judgement=judgement)


def run(repo: Path, *, base: str | None, default_branch: str, path_glob: str | None) -> dict[str, Any]:
    branch = collect(repo, base=base, default_branch=default_branch, path_glob=path_glob)
    counts = {k: sum(1 for s, _ in branch.files if s == k) for k in ("A", "M", "D")}
    summary = {
        "base": branch.base,
        "commits": len(branch.commits),
        "files": len(branch.files),
        "added": counts["A"],
        "modified": counts["M"],
        "deleted": counts["D"],
    }
    if not branch.commits:
        return {
            "summary": summary,
            "nothing_to_check": True,
            "message": f"Nothing to check — no commits ahead of `{branch.base}`",
        }
    return {
        "summary": summary,
        "nothing_to_check": False,
        "categories": {
            "spdx_headers": check_spdx(branch, expected_license(repo)),
            "commit_shape": check_commits(branch, attribution_convention(repo)),
            "placeholder_convention": check_placeholders(branch),
            "contributing_conventions": check_contributing(branch),
        },
        "added_lines": dict(branch.added_lines),
    }
