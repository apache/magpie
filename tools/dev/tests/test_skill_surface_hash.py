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


def test_inputs_are_requires_config_and_anchors() -> None:
    requires, anchors = MOD.surface_inputs(SKILL)
    assert requires == ["demo.md", "project.md"]
    assert anchors == [
        "Golden rule 1 — propose, never apply.",
        "Step 1 — gather",
        "Step 1a — the narrow case",
    ]


def test_preflight_block_is_excluded() -> None:
    _, anchors = MOD.surface_inputs(SKILL)
    assert not any("Pre-flight" in a for a in anchors)


def test_prose_edit_does_not_move_the_hash() -> None:
    reworded = SKILL.replace("Some prose that may be reworded freely.", "Entirely different prose here.")
    assert MOD.surface_hash(reworded) == MOD.surface_hash(SKILL)


def test_renamed_heading_moves_the_hash() -> None:
    renamed = SKILL.replace("## Step 1 — gather", "## Step 1 — collect")
    assert MOD.surface_hash(renamed) != MOD.surface_hash(SKILL)


def test_changed_requires_config_moves_the_hash() -> None:
    changed = SKILL.replace("  - demo.md\n", "  - demo.md\n  - extra.md\n")
    assert MOD.surface_hash(changed) != MOD.surface_hash(SKILL)


def test_requires_config_order_does_not_matter() -> None:
    reordered = SKILL.replace("  - project.md\n  - demo.md\n", "  - demo.md\n  - project.md\n")
    assert MOD.surface_hash(reordered) == MOD.surface_hash(SKILL)


def test_apply_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text(SKILL)
    digest = MOD.surface_hash(SKILL)
    assert MOD.apply(path, digest) == (True, None)
    first = path.read_text()
    assert MOD.apply(path, digest) == (False, None)
    assert path.read_text() == first
    assert f"surface_hash: {digest}" in first


def test_apply_replaces_a_stale_value(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text(SKILL.replace("license: Apache-2.0", "surface_hash: sha256:dead\nlicense: Apache-2.0"))
    digest = MOD.surface_hash(path.read_text())
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
        if f"surface_hash: {MOD.surface_hash(p.read_text())}" not in p.read_text()
    ]
    assert stale == [], f"run `python3 tools/dev/skill-surface-hash.py --fix`: {stale}"
