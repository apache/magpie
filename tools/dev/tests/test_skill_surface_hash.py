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

"""Tests for `skill-surface-hash.py`, the generator that stamps a
reconciliation fingerprint into every `skills/*/SKILL.md`."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "skill_surface_hash", REPO / "tools" / "dev" / "skill-surface-hash.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load()

SKILL = """---
name: magpie-demo
family: issue
requires_config:
  - project.md
  - demo.md
description: |
  A demo skill.
license: Apache-2.0
---

# Demo skill

<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->

## Pre-flight — is this project set up?

Shared text that every skill carries.

<!-- END MAGPIE PREFLIGHT -->

## Step 1 — gather

Some prose that may be reworded freely.

**Golden rule 1 — propose, never apply.**

### Step 1a — the narrow case
"""


def _make_skill(root: Path, skill_md: str = SKILL, **details: str) -> Path:
    """Build a skill directory at `root`: `SKILL.md` plus any sibling
    `*.md` detail files named by `details` (e.g. `**{"guide.md": "..."}`)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(skill_md)
    for name, content in details.items():
        (root / name).write_text(content)
    return root


def test_inputs_are_requires_config_and_anchors(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    requires, anchors = MOD.surface_inputs(skill_dir)
    assert requires == ["demo.md", "project.md"]
    assert anchors == [
        "Golden rule 1 — propose, never apply.",
        "Step 1 — gather",
        "Step 1a — the narrow case",
    ]


def test_preflight_block_is_excluded(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    _, anchors = MOD.surface_inputs(skill_dir)
    assert not any("Pre-flight" in a for a in anchors)


def test_prose_edit_does_not_move_the_hash(tmp_path: Path) -> None:
    reworded = SKILL.replace("Some prose that may be reworded freely.", "Entirely different prose here.")
    base = _make_skill(tmp_path / "base")
    changed = _make_skill(tmp_path / "changed", reworded)
    assert MOD.surface_hash(changed) == MOD.surface_hash(base)


def test_renamed_heading_moves_the_hash(tmp_path: Path) -> None:
    renamed = SKILL.replace("## Step 1 — gather", "## Step 1 — collect")
    base = _make_skill(tmp_path / "base")
    changed = _make_skill(tmp_path / "changed", renamed)
    assert MOD.surface_hash(changed) != MOD.surface_hash(base)


def test_changed_requires_config_moves_the_hash(tmp_path: Path) -> None:
    changed_text = SKILL.replace("  - demo.md\n", "  - demo.md\n  - extra.md\n")
    base = _make_skill(tmp_path / "base")
    changed = _make_skill(tmp_path / "changed", changed_text)
    assert MOD.surface_hash(changed) != MOD.surface_hash(base)


def test_requires_config_order_does_not_matter(tmp_path: Path) -> None:
    reordered_text = SKILL.replace("  - project.md\n  - demo.md\n", "  - demo.md\n  - project.md\n")
    base = _make_skill(tmp_path / "base")
    reordered = _make_skill(tmp_path / "reordered", reordered_text)
    assert MOD.surface_hash(reordered) == MOD.surface_hash(base)


def test_heading_renamed_in_detail_file_moves_the_hash(tmp_path: Path) -> None:
    detail = "## Detail heading\n\nSome detail prose.\n"
    renamed_detail = "## Detail heading renamed\n\nSome detail prose.\n"
    base = _make_skill(tmp_path / "base", SKILL, **{"guide.md": detail})
    renamed = _make_skill(tmp_path / "renamed", SKILL, **{"guide.md": renamed_detail})
    assert MOD.surface_hash(renamed) != MOD.surface_hash(base)


def test_prose_edit_in_detail_file_does_not_move_the_hash(tmp_path: Path) -> None:
    detail = "## Detail heading\n\nOriginal detail prose.\n"
    reworded_detail = "## Detail heading\n\nCompletely different detail prose.\n"
    base = _make_skill(tmp_path / "base", SKILL, **{"guide.md": detail})
    reworded = _make_skill(tmp_path / "reworded", SKILL, **{"guide.md": reworded_detail})
    assert MOD.surface_hash(reworded) == MOD.surface_hash(base)


def test_adding_a_detail_file_moves_the_hash(tmp_path: Path) -> None:
    without = _make_skill(tmp_path / "without")
    with_detail = _make_skill(tmp_path / "with-detail", SKILL, **{"guide.md": "## New heading\n"})
    assert MOD.surface_hash(with_detail) != MOD.surface_hash(without)


def test_swapping_anchors_between_detail_files_moves_the_hash(tmp_path: Path) -> None:
    """Same combined anchor text, split the opposite way across two detail
    files, must hash differently — the file an anchor came from is part of
    the payload, not just the anchor text. Rename-within-a-file and
    add-a-file coverage would not catch a regression that dropped the
    per-file tagging; this is the property that would."""
    swapped_a = _make_skill(
        tmp_path / "swapped-a",
        SKILL,
        **{"alpha.md": "## Heading One\n", "beta.md": "## Heading Two\n"},
    )
    swapped_b = _make_skill(
        tmp_path / "swapped-b",
        SKILL,
        **{"alpha.md": "## Heading Two\n", "beta.md": "## Heading One\n"},
    )
    assert MOD.surface_hash(swapped_a) != MOD.surface_hash(swapped_b)


def test_hash_does_not_depend_on_file_creation_order(tmp_path: Path) -> None:
    forward = tmp_path / "forward"
    forward.mkdir()
    (forward / "SKILL.md").write_text(SKILL)
    (forward / "alpha.md").write_text("## Alpha heading\n")
    (forward / "zulu.md").write_text("## Zulu heading\n")

    reverse = tmp_path / "reverse"
    reverse.mkdir()
    (reverse / "zulu.md").write_text("## Zulu heading\n")
    (reverse / "alpha.md").write_text("## Alpha heading\n")
    (reverse / "SKILL.md").write_text(SKILL)

    assert MOD.surface_hash(forward) == MOD.surface_hash(reverse)


def test_no_detail_files_matches_legacy_text_only_algorithm(tmp_path: Path) -> None:
    """A skill directory with no detail files must hash exactly as the
    pre-widening algorithm (over `SKILL.md`'s own text alone) did, so the
    57 single-file skills do not churn when the generator is widened."""
    skill_dir = _make_skill(tmp_path)

    front = MOD.FRONTMATTER_RE.match(SKILL)
    assert front is not None
    body = MOD.PREFLIGHT_RE.sub("", SKILL[front.end() :])
    requires_block = MOD.REQUIRES_RE.search(front.group(1) + "\n")
    assert requires_block is not None
    legacy_requires = sorted(MOD.ITEM_RE.findall(requires_block.group(1)))
    legacy_anchors = sorted(
        {MOD._normalise(m) for m in MOD.HEADING_RE.findall(body)}
        | {MOD._normalise(m) for m in MOD.GOLDEN_RE.findall(body)}
    )
    legacy_payload = "\n".join(["requires_config:", *legacy_requires, "anchors:", *legacy_anchors])
    legacy_digest = "sha256:" + hashlib.sha256(legacy_payload.encode()).hexdigest()[:16]

    assert MOD.surface_hash(skill_dir) == legacy_digest


def test_subdirectories_are_ignored(tmp_path: Path) -> None:
    without = _make_skill(tmp_path / "without")

    with_subdirs = _make_skill(tmp_path / "with-subdirs")
    guards = with_subdirs / "guards"
    guards.mkdir()
    (guards / "check.py").write_text("# not markdown, and not top-level\n")
    (guards / "notes.md").write_text("## Should be ignored\n")
    fixtures = with_subdirs / "fixtures"
    fixtures.mkdir()
    (fixtures / "case.md").write_text("## Also ignored\n")

    assert MOD.surface_hash(with_subdirs) == MOD.surface_hash(without)


def test_apply_is_idempotent(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    path = skill_dir / "SKILL.md"
    digest = MOD.surface_hash(skill_dir)
    assert MOD.apply(path, digest) == (True, None)
    first = path.read_text()
    assert MOD.apply(path, digest) == (False, None)
    assert path.read_text() == first
    assert f"surface_hash: {digest}" in first


def test_apply_replaces_a_stale_value(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text(SKILL.replace("license: Apache-2.0", "surface_hash: sha256:dead\nlicense: Apache-2.0"))
    digest = MOD.surface_hash(tmp_path)
    assert MOD.apply(path, digest) == (True, None)
    assert "sha256:dead" not in path.read_text()


def test_missing_frontmatter_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text("# No frontmatter\n")
    changed, error = MOD.apply(path, "sha256:abc")
    assert changed is False
    assert error is not None and "frontmatter" in error


def test_every_live_skill_is_current() -> None:
    stale = [
        p
        for p in sorted((REPO / "skills").glob("*/SKILL.md"))
        if f"surface_hash: {MOD.surface_hash(p.parent)}" not in p.read_text()
    ]
    assert stale == [], f"run `python3 tools/dev/skill-surface-hash.py --fix`: {stale}"
