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
"""Every vetted operation a doc runs under a caller is granted to that caller.

Adopters, `setup reconcile` and the isolated setup take their policy grants
from the `[callers]` example in the vetted-ops README. A skill doc that runs
`vetted-op-read --caller security-issue-triage issue-search …` while the
example does not grant `issue-search` to that caller is refused on every
adopter, and the run either stops or (worse) borrows another skill's caller.
This test reads every `vetted-op`, `vetted-op-read`, `vetted-op-tracker` and
`vetted-op-git` call in the repository's Markdown (skills, the shared blocks
they include, tool READMEs and docs) and checks each named operation against
the example. `test_publish_grants.py` covers the `vetted-git-publish` block's
prose list of steps, which names operations without a `--caller` call each.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from vetted_ops import cli, git_ops
from vetted_ops import ops as ops_mod

REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "tools" / "vetted-ops" / "README.md"

#: The dispatcher entry points, as a whole word (not `vetted-ops`, `vetted-op-checks`).
ENTRY = re.compile(r"(?<![\w/-])vetted-op(?:-read|-tracker|-git)?(?![\w-])")
#: Flags that take a value; every other `--flag` is boolean (`--dry-run`).
VALUE_FLAGS = {"--caller", "--config", "--save", "--policy-from"}
#: Subcommands that are not operations and need no grant (`batch-check` only
#: validates a manifest whose entries need the grants themselves).
META = {"policy", "list-ops", "approval-status", "source", "batch-check"}
NAME = re.compile(r"[a-z][a-z0-9-]*")
#: Punctuation a call picks up from the surrounding prose or code span.
TRIM = "`'\",.;:)"

#: Operations a caller's docs name but it does not need, and why. The
#: draft-PR flows open their pull request with `gh pr create --web --draft`
#: (the `vetted-git-publish` block's fallback), so they never label one
#: through vetted-ops; `test_publish_grants.py` carries the same exception.
NOT_NEEDED: dict[str, set[str]] = {
    "issue-fix-workflow": {"pr-add-label"},
    "audit-finding-fix": {"pr-add-label"},
    "release-prepare": {"pr-add-label"},
}


def _known_ops() -> set[str]:
    _ = cli  # importing the CLI registers every operation module
    return set(ops_mod.OPS) | set(git_ops.OPS)


def _template_grants() -> dict[str, set[str]]:
    grants: dict[str, set[str]] = {}
    for toml in re.findall(r"```toml\n(.*?)```", README.read_text(encoding="utf-8"), re.S):
        if "[callers]" in toml:
            for caller, ops in tomllib.loads(toml).get("callers", {}).items():
                grants.setdefault(caller, set()).update(ops)
    return grants


def calls(text: str) -> list[tuple[str, str]]:
    """`(caller, operation)` for each dispatcher call in `text` that names both.

    A shell line continuation joins the next line first. The call ends at the
    end of its line; flags may come in any order before the operation. A call
    whose caller or operation is a placeholder (`<caller>`, `<operation>`) is
    a template, not a call, and is skipped.
    """
    text = re.sub(r"\\\n\s*", " ", text)
    found: list[tuple[str, str]] = []
    for match in ENTRY.finditer(text):
        tokens = text[match.end() :].split("\n", 1)[0].split()
        caller = operation = None
        i = 0
        while i < len(tokens):
            token = tokens[i].strip(TRIM)
            if token in VALUE_FLAGS:
                if token == "--caller" and i + 1 < len(tokens):
                    caller = tokens[i + 1].strip(TRIM)
                i += 2
                continue
            if token.startswith("--"):
                i += 1
                continue
            operation = token
            break
        if (
            caller
            and operation
            and operation not in META
            and NAME.fullmatch(caller)
            and NAME.fullmatch(operation)
        ):
            found.append((caller, operation))
    return found


def _docs() -> list[Path]:
    """The repository's Markdown, without mirrors, tests, eval fixtures or vendored trees."""
    skip = ("/.venv/", "/node_modules/", "/tests/")
    found = []
    for path in sorted(REPO_ROOT.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part in f"/{rel}" for part in skip) or rel.startswith((".git/", "tools/skill-evals/evals/")):
            continue
        if re.match(r"plugins/[^/]+/tools/", rel):  # byte-identical mirrors of tools/
            continue
        found.append(path)
    return found


def _named_calls() -> dict[tuple[str, str], list[str]]:
    named: dict[tuple[str, str], list[str]] = {}
    for path in _docs():
        rel = path.relative_to(REPO_ROOT).as_posix()
        for pair in calls(path.read_text(encoding="utf-8", errors="replace")):
            named.setdefault(pair, []).append(rel)
    return named


def test_the_parser_reads_the_call_shapes_the_docs_use() -> None:
    text = (
        "uvx --from ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-triage "
        'issue-list-label open "<label>"\n'
        "uv run --project ~/.claude/magpie/vetted-ops \\\n"
        "  vetted-op-read --caller security-issue-import \\\n"
        "  --save security-import-index.json issue-list-with-bodies\n"
        "(`vetted-op --caller security-issue-invalidate advisory-comment <GHSA> <file>`)\n"
        "vetted-op-read --save pages.json --caller pr-management-triage <sweep operation>\n"
        "vetted-op-read --caller <caller> issue-view <N>\n"
        "vetted-op-read --caller security-issue-sync policy\n"
        "vetted-op-git --dry-run --caller setup-upstream-fix git-commit <file>\n"
        "uv run --project ~/.claude/magpie/vetted-ops vetted-ops-is-not-an-entry --caller x y\n"
    )
    assert calls(text) == [
        ("security-issue-triage", "issue-list-label"),
        ("security-issue-import", "issue-list-with-bodies"),
        ("security-issue-invalidate", "advisory-comment"),
        ("setup-upstream-fix", "git-commit"),
    ]


def test_the_scan_finds_the_security_skills_calls() -> None:
    named = _named_calls()
    for pair in [
        ("security-issue-triage", "issue-comment"),
        ("security-issue-triage", "issue-list-label"),
        ("security-issue-triage", "issue-search"),
        ("security-issue-import", "issue-search"),
        ("security-issue-import", "advisory-view"),
        ("security-issue-import", "repo-pr-search"),
        ("security-issue-sync", "rollup-append"),
        ("security-issue-sync", "repo-pr-search"),
        ("security-issue-import-from-scan", "issue-list-with-bodies"),
        ("security-issue-import-from-scan", "compare"),
        ("security-issue-import-from-scan", "issue-comment"),
    ]:
        assert pair in named, f"no doc runs {pair[1]} as {pair[0]}"


def test_every_named_operation_exists() -> None:
    known = _known_ops()
    unknown = {pair: files for pair, files in _named_calls().items() if pair[1] not in known}
    assert not unknown, f"docs run operations vetted-ops does not have: {unknown}"


@pytest.mark.parametrize("caller", sorted({caller for caller, _ in _named_calls()}))
def test_the_readme_template_grants_what_the_docs_run(caller: str) -> None:
    granted = _template_grants().get(caller, set()) | NOT_NEEDED.get(caller, set())
    known = _known_ops()
    missing = {
        op: files
        for (who, op), files in sorted(_named_calls().items())
        if who == caller and op in known and op not in granted
    }
    assert not missing, f"{README.relative_to(REPO_ROOT)} does not grant {caller}: {missing}"


#: Body directories the dispatchers never read from: a body file lives only under the policy's
#: `workspace`, so a doc naming another directory sends the write to a refusal.
STALE_BODY_DIRS = ("apache-magpie/vetted-ops-bodies",)


def test_no_doc_or_hook_names_a_body_directory_other_than_the_workspace() -> None:
    sources = [*_docs(), *sorted(REPO_ROOT.glob("plugins/*/hooks/*.ts"))]
    stale = {
        path.relative_to(REPO_ROOT).as_posix(): marker
        for path in sources
        for marker in STALE_BODY_DIRS
        if marker in path.read_text(encoding="utf-8", errors="replace")
    }
    assert not stale, f"name the policy's `workspace` (`vetted-op-read policy` prints it) instead: {stale}"
