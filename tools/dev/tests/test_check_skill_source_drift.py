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

"""Tests for ``check-skill-source-drift.py``.

The GitHub API is replaced by a dict of canned responses, so nothing here
touches the network. What matters: an in-sync catalogue passes, and each kind
of upstream change (a new skill, a removed one, a re-layout, a first tag, a
newer tag, a moved tag, a marketplace change) is reported as drift.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "check-skill-source-drift.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_skill_source_drift", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()

PIN = "a" * 40
BASE = "/repos/apache/incubator"

ORG_FILE = """\
# Curated

<!-- BEGIN SKILL-SOURCE CATALOGUE: apache-incubator -->
| Skill | What it does | Install through Magpie | Marketplaces |
|---|---|---|---|
| `releasecheck` | Checks an RC. | `pinned` | `claude-code`, `codex` |
| `maturity` | Evidence pack. | `untagged` | — |
| `graduation` | Readiness. | `single-file` | — |
| `archaeology` | Draft. | `draft` | — |
<!-- END SKILL-SOURCE CATALOGUE: apache-incubator -->

```yaml
- id: apache-incubator
  organization: ASF
  name: "Apache Incubator skills"
  method: git-tag
  url: https://github.com/apache/incubator
  ref: releasecheck-0.5.1
  commit: {pin}
  layout:
    skills_root: tools/skills
  provides:
    - skill: releasecheck
```
"""


def _entries(*items: tuple[str, str]) -> list[dict[str, str]]:
    return [{"name": n, "type": t} for n, t in items]


def _catalog(data: object) -> dict[str, str]:
    return {"content": base64.b64encode(json.dumps(data).encode()).decode()}


def _responses() -> dict[str, object]:
    market = {"plugins": [{"name": "releasecheck"}]}
    return {
        f"{BASE}/contents/tools/skills": _entries(
            ("README.md", "file"),
            ("graduation.md", "file"),
            ("releasecheck", "dir"),
            ("maturity", "dir"),
            ("draft", "dir"),
            ("evals", "dir"),
        ),
        f"{BASE}/contents/tools/skills/releasecheck": _entries(("SKILL.md", "file")),
        f"{BASE}/contents/tools/skills/maturity": _entries(("SKILL.md", "file"), ("references", "dir")),
        f"{BASE}/contents/tools/skills/draft": _entries(("archaeology.md", "file")),
        f"{BASE}/contents/tools/skills/evals": _entries(("run-evals.sh", "file")),
        f"{BASE}/contents/tools/skills/releasecheck?ref=releasecheck-0.5.1": _entries(("SKILL.md", "file")),
        f"{BASE}/git/matching-refs/tags/": [
            {"ref": "refs/tags/releasecheck-0.5"},
            {"ref": "refs/tags/releasecheck-0.5.1"},
            {"ref": "refs/tags/releases/tools/1.0.0"},
        ],
        f"{BASE}/git/ref/tags/releasecheck-0.5.1": {"object": {"type": "tag", "sha": "t1"}},
        f"{BASE}/git/tags/t1": {"object": {"type": "commit", "sha": PIN}},
        f"{BASE}/contents/.claude-plugin/marketplace.json": _catalog(market),
        f"{BASE}/contents/.agents/plugins/marketplace.json": _catalog(market),
    }


def _run(tmp_path: Path, responses: dict[str, object], org_file: str = ORG_FILE) -> tuple[int, str]:
    org = tmp_path / "organizations" / "ASF"
    org.mkdir(parents=True)
    (org / "skill-sources.md").write_text(org_file.replace("{pin}", PIN), encoding="utf-8")
    return mod.run(tmp_path, responses.get)


def test_in_sync(tmp_path: Path) -> None:
    status, report = _run(tmp_path, _responses())
    assert status == 0, report
    assert "In sync." in report


def test_new_skill_upstream(tmp_path: Path) -> None:
    responses = _responses()
    listing = responses[f"{BASE}/contents/tools/skills"]
    assert isinstance(listing, list)
    listing.append({"name": "board-report.md", "type": "file"})
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "**New skill** `board-report` (single-file)" in report


def test_removed_skill(tmp_path: Path) -> None:
    responses = _responses()
    responses[f"{BASE}/contents/tools/skills/draft"] = []
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "`archaeology` is in the catalogue but the source no longer ships it" in report


def test_single_file_became_directory(tmp_path: Path) -> None:
    responses = _responses()
    listing = responses[f"{BASE}/contents/tools/skills"]
    assert isinstance(listing, list)
    listing.remove({"name": "graduation.md", "type": "file"})
    listing.append({"name": "graduation", "type": "dir"})
    responses[f"{BASE}/contents/tools/skills/graduation"] = _entries(("SKILL.md", "file"))
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "`graduation` is catalogued `single-file`, but the source makes it `untagged`" in report


def test_first_tag_for_unpinned_skill(tmp_path: Path) -> None:
    responses = _responses()
    tags = responses[f"{BASE}/git/matching-refs/tags/"]
    assert isinstance(tags, list)
    tags.append({"ref": "refs/tags/maturity-0.1"})
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "**Tagged** `maturity` is now tagged (`maturity-0.1`)" in report


def test_newer_tag_for_pinned_skill(tmp_path: Path) -> None:
    responses = _responses()
    tags = responses[f"{BASE}/git/matching-refs/tags/"]
    assert isinstance(tags, list)
    tags.append({"ref": "refs/tags/releasecheck-0.10"})
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "**Newer tag** `releasecheck-0.10`" in report


def test_moved_tag(tmp_path: Path) -> None:
    responses = _responses()
    responses[f"{BASE}/git/tags/t1"] = {"object": {"type": "commit", "sha": "b" * 40}}
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "**Pinned tag moved.**" in report


def test_missing_tag(tmp_path: Path) -> None:
    responses = _responses()
    del responses[f"{BASE}/git/ref/tags/releasecheck-0.5.1"]
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "**Pinned tag missing.**" in report


def test_marketplace_change(tmp_path: Path) -> None:
    responses = _responses()
    market = {"plugins": [{"name": "releasecheck"}, {"name": "maturity"}]}
    responses[f"{BASE}/contents/marketplace.json"] = _catalog(market)
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "`maturity` installs from these marketplaces: copilot; the catalogue says none" in report


def test_unknown_marketplace_is_an_error(tmp_path: Path) -> None:
    org_file = ORG_FILE.replace("`claude-code`, `codex` |", "`claude-code`, `nowhere` |")
    with pytest.raises(mod.CheckError, match="unknown marketplace"):
        _run(tmp_path, _responses(), org_file)


def test_provided_skill_not_a_directory_at_pin(tmp_path: Path) -> None:
    responses = _responses()
    responses[f"{BASE}/contents/tools/skills/releasecheck?ref=releasecheck-0.5.1"] = None
    status, report = _run(tmp_path, responses)
    assert status == 1
    assert "is in `apache-incubator`'s `provides` but is not a" in report


def test_catalogue_without_descriptor_is_an_error(tmp_path: Path) -> None:
    org_file = ORG_FILE.replace("CATALOGUE: apache-incubator", "CATALOGUE: elsewhere")
    with pytest.raises(mod.CheckError, match="unknown source"):
        _run(tmp_path, _responses(), org_file)


def test_descriptor_without_catalogue_is_drift(tmp_path: Path) -> None:
    start = ORG_FILE.index("<!-- BEGIN")
    end = ORG_FILE.index("-->", ORG_FILE.index("<!-- END")) + 3
    status, report = _run(tmp_path, _responses(), ORG_FILE[:start] + ORG_FILE[end:])
    assert status == 1
    assert "No catalogue for `https://github.com/apache/incubator`" in report


def test_commented_and_placeholder_descriptors_are_ignored() -> None:
    text = "```yaml\n# - id: commented\n- id: <source-id>\n  url: x\n```\n"
    assert mod.parse_descriptors(text) == []


PER_SKILL = ORG_FILE.replace(
    "```\n",
    "```\n\n```yaml\n- id: apache-incubator-maturity\n  organization: ASF\n  name: x\n"
    "  method: git-tag\n  url: https://github.com/apache/incubator\n  ref: maturity-0.1\n"
    "  commit: {pin}\n  layout:\n    skills_root: tools/skills\n  provides:\n    - skill: maturity\n```\n",
    1,
).replace("| `maturity` | Evidence pack. | `untagged` |", "| `maturity` | Evidence pack. | `pinned` |")


def _with_maturity_tag(responses: dict[str, object]) -> dict[str, object]:
    tags = responses[f"{BASE}/git/matching-refs/tags/"]
    assert isinstance(tags, list)
    tags.append({"ref": "refs/tags/maturity-0.1"})
    responses[f"{BASE}/git/ref/tags/maturity-0.1"] = {"object": {"type": "commit", "sha": PIN}}
    responses[f"{BASE}/contents/tools/skills/maturity?ref=maturity-0.1"] = _entries(("SKILL.md", "file"))
    return responses


def test_per_skill_descriptors_share_one_catalogue(tmp_path: Path) -> None:
    status, report = _run(tmp_path, _with_maturity_tag(_responses()), PER_SKILL)
    assert status == 0, report
    assert report.count("### ") == 1


def test_newer_tag_for_a_per_skill_pin(tmp_path: Path) -> None:
    responses = _with_maturity_tag(_responses())
    tags = responses[f"{BASE}/git/matching-refs/tags/"]
    assert isinstance(tags, list)
    tags.append({"ref": "refs/tags/maturity-0.2"})
    status, report = _run(tmp_path, responses, PER_SKILL)
    assert status == 1
    assert "**Newer tag** `maturity-0.2` for `apache-incubator-maturity`" in report
