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
"""Comparing a project's skill-source pins with its organization's catalogue."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from setup_preflight import skill_sources

from .conftest import personal, write_lock

REPO_ROOT = Path(__file__).resolve().parents[3]
ASF_CATALOGUE = REPO_ROOT / "organizations" / "ASF" / "skill-sources.md"

CATALOGUE = """
# ASF

```yaml
- id: apache-incubator-releasecheck
  organization: ASF
  name: "Apache Incubator skills"
  method: git-tag
  url: https://github.com/apache/incubator
  marketplace: apache-incubator
  ref: releasecheck-0.6.0
  commit: bbbb
  provides:
    - skill: releasecheck
- id: apache-incubator-board-report
  method: git-tag
  url: https://github.com/apache/incubator
  ref: board-report-1.0.0
  commit: cccc
```
"""


def trust_list(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "skill-sources.md"
    path.write_text(f"# Trusted\n\n```yaml\n{body}```\n", encoding="utf-8")
    return path


def catalogue(tmp_path: Path) -> Path:
    path = tmp_path / "catalogue.md"
    path.write_text(CATALOGUE, encoding="utf-8")
    return path


def states(project: Path, tmp_path: Path, body: str) -> dict[str, str | None]:
    rows = skill_sources.pins(project, trust_list(tmp_path, body), catalogue(tmp_path))
    return {str(row["id"]): row["state"] for row in rows}


@pytest.mark.parametrize(
    ("entry", "state"),
    [
        ("  ref: releasecheck-0.5.1\n  commit: aaaa\n", "moved"),
        ("  ref: releasecheck-0.6.0\n  commit: bbbb\n", "same"),
        ("  ref: releasecheck-0.6.0\n  commit: ffff\n", "tag-moved"),
        ("  ref: releasecheck-0.7.0\n  commit: dddd\n", "adopter-ahead"),
        ("  ref: main\n", "not-comparable"),
        ("  ref: other-skill-0.1.0\n", "not-comparable"),
        ("  method: git-tag\n  url: https://example.org/fork\n  ref: releasecheck-0.1.0\n", "not-curated"),
    ],
)
def test_each_pin_state(project: Path, tmp_path: Path, entry: str, state: str) -> None:
    assert states(project, tmp_path, f"- id: apache-incubator-releasecheck\n{entry}") == {
        "apache-incubator-releasecheck": state
    }


def test_an_id_the_catalogue_does_not_carry_is_not_curated(project: Path, tmp_path: Path) -> None:
    assert states(project, tmp_path, "- id: someone-else\n  ref: x-1.0.0\n") == {
        "someone-else": "not-curated"
    }


def test_the_commented_template_examples_declare_nothing(project: Path, tmp_path: Path) -> None:
    body = "# - id: <org-curated-source-id>\n#   ref: <tag>\n"
    assert skill_sources.pins(project, trust_list(tmp_path, body), catalogue(tmp_path)) == []


def test_no_catalogue_leaves_every_source_uncurated(project: Path, tmp_path: Path) -> None:
    rows = skill_sources.pins(
        project,
        trust_list(tmp_path, "- id: apache-incubator-releasecheck\n  ref: releasecheck-0.5.1\n"),
        None,
    )
    assert [row["state"] for row in rows] == ["not-curated"]


def test_a_declined_bump_is_asked_again_only_when_the_curator_moves_on(project: Path, tmp_path: Path) -> None:
    body = "- id: apache-incubator-releasecheck\n  ref: releasecheck-0.5.1\n  commit: aaaa\n"
    personal(project).mkdir(parents=True)
    skill_sources.decline(
        project, "apache-incubator-releasecheck", "releasecheck-0.6.0", today=date(2026, 11, 26)
    )
    assert states(project, tmp_path, body) == {"apache-incubator-releasecheck": "declined"}
    stamp = json.loads((personal(project) / "reconciled.json").read_text())
    assert stamp["skill_source_pins"]["apache-incubator-releasecheck"] == {
        "declined": "releasecheck-0.6.0",
        "at": "2026-11-26",
    }
    newer = catalogue(tmp_path)
    newer.write_text(CATALOGUE.replace("releasecheck-0.6.0", "releasecheck-0.7.0"), encoding="utf-8")
    rows = skill_sources.pins(project, trust_list(tmp_path, body), newer)
    assert [row["state"] for row in rows] == ["moved"]


def test_decline_keeps_every_other_record(project: Path, tmp_path: Path) -> None:
    personal(project).mkdir(parents=True)
    (personal(project) / "reconciled.json").write_text(json.dumps({"welcome": {"x": 1}}), encoding="utf-8")
    skill_sources.decline(project, "a", "a-1.0.0")
    stamp = json.loads((personal(project) / "reconciled.json").read_text())
    assert stamp["welcome"] == {"x": 1} and stamp["skill_source_pins"]["a"]["declined"] == "a-1.0.0"


def test_decline_never_overwrites_a_stamp_it_cannot_parse(project: Path) -> None:
    personal(project).mkdir(parents=True)
    (personal(project) / "reconciled.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        skill_sources.decline(project, "a", "a-1.0.0")
    assert (personal(project) / "reconciled.json").read_text() == "not json"


def test_a_linked_worktree_inherits_a_decline_recorded_in_its_main_checkout(tmp_path: Path) -> None:
    main = tmp_path / "main"
    gitdir = main / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    for root in (main, wt):
        write_lock(root, "method: local\n")
        (root / ".apache-magpie-local").mkdir()
    skill_sources.decline(main, "apache-incubator-releasecheck", "releasecheck-0.6.0")
    body = "- id: apache-incubator-releasecheck\n  ref: releasecheck-0.5.1\n"
    assert states(wt, tmp_path, body) == {"apache-incubator-releasecheck": "declined"}


def test_the_shipped_asf_catalogue_parses() -> None:
    curated = skill_sources.parse_descriptors(ASF_CATALOGUE.read_text(encoding="utf-8"))
    entry = curated["apache-incubator-releasecheck"]
    assert entry["marketplace"] == "apache-incubator"
    assert entry["ref"].startswith("releasecheck-")
    assert "apache-incubator" not in curated  # renamed; the name is the marketplace's


def test_versions_are_read_as_the_drift_check_reads_them() -> None:
    drift = (REPO_ROOT / "tools" / "dev" / "check-skill-source-drift.py").read_text(encoding="utf-8")
    match = re.search(r'_VERSIONED_REF_RE = re\.compile\(r"(.+)"\)', drift)
    assert match is not None
    assert match.group(1) == skill_sources._VERSIONED_REF.pattern


def test_cli_prints_the_rows(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    listed = trust_list(tmp_path, "- id: apache-incubator-releasecheck\n  ref: releasecheck-0.5.1\n")
    code = skill_sources.main(
        [
            "pins",
            "--project-root",
            str(project),
            "--trust-list",
            str(listed),
            "--catalogue",
            str(catalogue(tmp_path)),
        ]
    )
    assert code == 0
    [row] = json.loads(capsys.readouterr().out)
    assert row["state"] == "moved" and row["curated_ref"] == "releasecheck-0.6.0"


@pytest.mark.parametrize(
    "fence",
    [
        "- id: apache-incubator-releasecheck  # the curated one\n  ref: releasecheck-0.5.1  # pinned 2026-11\n",
        "  - id: apache-incubator-releasecheck\n    ref: releasecheck-0.5.1\n",
        "id: apache-incubator-releasecheck\nref: releasecheck-0.5.1\n",
    ],
    ids=["inline-comments", "indented-list", "bare-mapping"],
)
def test_every_documented_descriptor_form_is_read(project: Path, tmp_path: Path, fence: str) -> None:
    assert states(project, tmp_path, fence) == {"apache-incubator-releasecheck": "moved"}


def test_a_nested_block_never_bleeds_into_the_entry_or_the_next(tmp_path: Path) -> None:
    text = (
        "```yaml\n- id: one\n  ref: one-1.0.0\n  layout:\n    ref: nested-9.9.9\n"
        "  provides:\n    - skill: one\n- id: two\n  ref: two-2.0.0\n```\n"
    )
    parsed = skill_sources.parse_descriptors(text)
    assert parsed["one"]["ref"] == "one-1.0.0"
    assert parsed["two"] == {"id": "two", "ref": "two-2.0.0"}


ARCHIVE_CATALOGUE = """```yaml
- id: foo-archive
  method: svn-zip
  url: https://dist.apache.org/repos/dist/release/foo/foo-skills-1.2.0.zip
  ref: foo-skills-1.2.0
  sha512: newhash
```
"""


@pytest.mark.parametrize(
    ("entry", "state"),
    [
        ("  ref: foo-skills-1.1.0\n  sha512: oldhash\n", "moved"),
        ("  ref: foo-skills-1.2.0\n  sha512: otherhash\n", "tag-moved"),
        ("  ref: foo-skills-1.2.0\n  sha512: newhash\n", "same"),
    ],
)
def test_an_archive_pin_compares_its_sha512(project: Path, tmp_path: Path, entry: str, state: str) -> None:
    cat = tmp_path / "archive.md"
    cat.write_text(ARCHIVE_CATALOGUE, encoding="utf-8")
    [row] = skill_sources.pins(project, trust_list(tmp_path, f"- id: foo-archive\n{entry}"), cat)
    assert row["state"] == state
    assert row["anchor_key"] == "sha512" and row["curated_anchor"] == "newhash"


def test_a_curated_pin_with_no_anchor_is_not_proposed(project: Path, tmp_path: Path) -> None:
    cat = tmp_path / "bare.md"
    cat.write_text("```yaml\n- id: x\n  method: git-tag\n  ref: x-2.0.0\n```\n", encoding="utf-8")
    [row] = skill_sources.pins(
        project, trust_list(tmp_path, "- id: x\n  ref: x-1.0.0\n  commit: aaaa\n"), cat
    )
    assert row["state"] == "not-comparable"


def test_a_decline_also_covers_a_lower_curated_version(project: Path, tmp_path: Path) -> None:
    skill_sources.decline(project, "apache-incubator-releasecheck", "releasecheck-0.7.0")
    body = "- id: apache-incubator-releasecheck\n  ref: releasecheck-0.5.1\n"
    assert states(project, tmp_path, body) == {"apache-incubator-releasecheck": "declined"}  # curated 0.6.0
