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

"""Tests for `check-shared-blocks.py`, the generator that owns every shared
prose block: the one **auto** block (`preflight`, inserted into every
non-`setup` `SKILL.md`, exactly as `check-skill-preflight.py` did) plus any
number of **declared** blocks (filled into a region a target already
carries, never inserted, sourced from `tools/dev/blocks/<name>.md`)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_shared_blocks", REPO / "tools" / "dev" / "check-shared-blocks.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load()

NON_EXEMPT_SKILL = """---
name: magpie-demo
family: issue
description: |
  A demo skill.
license: Apache-2.0
---

# Demo skill

## Step 1 — gather

Some prose.
"""

EXEMPT_SKILL = """---
name: magpie-setup-demo
family: setup
description: |
  A demo setup skill.
license: Apache-2.0
---

# Demo setup skill

## Step 1 — gather

Some prose.
"""


# --- the auto block: preflight ----------------------------------------------------


def test_auto_block_lands_in_non_exempt_skill(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(NON_EXEMPT_SKILL)

    block = MOD.preflight_block_text(REPO / "tools" / "dev" / "preflight-block.md")
    changed, error = MOD.apply_preflight(skill, block)
    assert (changed, error) == (True, None)

    text = skill.read_text()
    assert MOD.PREFLIGHT_BEGIN in text
    assert MOD.PREFLIGHT_END in text
    assert "Pre-flight — is this project set up?" in text


def test_auto_block_is_absent_from_exempt_skill(tmp_path: Path) -> None:
    """The exempt-family removal path: a `setup`-family skill must never
    carry the block, even if one was hand-added before it became exempt."""
    skill = tmp_path / "skills" / "setup-demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    block = MOD.preflight_block_text(REPO / "tools" / "dev" / "preflight-block.md")
    # Simulate a stale block already present in an exempt skill.
    stale = EXEMPT_SKILL.replace(
        "## Step 1 — gather",
        f"{block}\n## Step 1 — gather",
    )
    skill.write_text(stale)
    assert MOD.family_of(skill.read_text()) in MOD.EXEMPT_FAMILIES
    assert MOD.PREFLIGHT_RE.search(skill.read_text())

    new_text = MOD.PREFLIGHT_RE.sub("", skill.read_text())
    assert MOD.PREFLIGHT_BEGIN not in new_text


def test_auto_block_apply_is_idempotent(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(NON_EXEMPT_SKILL)
    block = MOD.preflight_block_text(REPO / "tools" / "dev" / "preflight-block.md")

    assert MOD.apply_preflight(skill, block) == (True, None)
    first = skill.read_text()
    assert MOD.apply_preflight(skill, block) == (False, None)
    assert skill.read_text() == first


def test_every_live_preflight_copy_is_byte_identical_to_regenerated() -> None:
    """The load-bearing guarantee: regenerating the auto block for every one
    of the live skills must reproduce exactly the text already committed —
    not merely 'the same after re-fixing', but identical to what is already
    there, since this test never writes anything."""
    block = MOD.preflight_block_text(REPO / "tools" / "dev" / "preflight-block.md")
    mismatches = []
    for path in sorted((REPO / "skills").glob("*/SKILL.md")):
        text = path.read_text()
        if MOD.family_of(text) in MOD.EXEMPT_FAMILIES:
            continue
        found = MOD.PREFLIGHT_RE.search(text)
        if not found or found.group(0).rstrip("\n") != block.rstrip("\n"):
            mismatches.append(path)
    assert mismatches == []


# --- declared blocks ----------------------------------------------------------------


def _declared_region(name: str, body: str = "") -> str:
    begin = f"<!-- BEGIN MAGPIE BLOCK: {name} — generated from tools/dev/blocks/{name}.md -->"
    end = f"<!-- END MAGPIE BLOCK: {name} -->"
    return f"{begin}\n{body}{end}\n"


def test_declared_region_is_filled(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Widget body text.\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    target.write_text(f"# Detail\n\n{_declared_region('widget')}\n## Next\n")

    new_text, errors = MOD.fill_declared(target.read_text(), blocks_dir=blocks_dir)
    assert errors == []
    assert "Widget body text." in new_text
    assert "## Next" in new_text


def test_declared_region_fill_is_idempotent(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Widget body text.\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    target.write_text(f"# Detail\n\n{_declared_region('widget')}\n## Next\n")

    changed, errors = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert (changed, errors) == (True, [])
    first = target.read_text()

    changed2, errors2 = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert (changed2, errors2) == (False, [])
    assert target.read_text() == first


def test_unknown_block_name_is_an_error_not_a_silent_skip(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()  # no "made-up.md" inside

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    target.write_text(f"# Detail\n\n{_declared_region('made-up')}\n")

    new_text, errors = MOD.fill_declared(target.read_text(), blocks_dir=blocks_dir)
    assert len(errors) == 1
    assert "made-up" in errors[0]
    # Left untouched — an unknown block is an error, not a silent skip that
    # quietly keeps whatever placeholder text was already there.
    assert new_text == target.read_text()


def test_declared_region_whose_source_is_missing_is_an_error(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    target.write_text(f"# Detail\n\n{_declared_region('ghost')}\n")

    changed, errors = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert changed is False
    assert errors and "ghost" in errors[0]
    # --fix must not write anything when it cannot resolve the source.
    assert "<!-- END MAGPIE BLOCK: ghost -->" in target.read_text()


def test_removing_a_declared_source_fails_rather_than_leaving_stale_text(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Original widget body.\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    target.write_text(f"# Detail\n\n{_declared_region('widget')}\n")

    changed, errors = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert (changed, errors) == (True, [])
    filled = target.read_text()
    assert "Original widget body." in filled

    (blocks_dir / "widget.md").unlink()

    changed2, errors2 = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert changed2 is False
    assert errors2 and "widget" in errors2[0]
    # The already-filled text stays exactly as it was — removing the source
    # must fail loudly, not silently leave (or silently blank) stale text.
    assert target.read_text() == filled


def test_target_outside_allowed_roots_is_rejected(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Widget body.\n")

    outside = tmp_path / "docs" / "notes.md"
    outside.parent.mkdir(parents=True)
    outside.write_text(f"# Notes\n\n{_declared_region('widget')}\n")

    changed, errors = MOD.process_declared(
        outside, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert changed is False
    assert errors and "allowed roots" in errors[0]
    # Untouched: the region must not have been filled from outside the root.
    assert "Widget body." not in outside.read_text()


def test_file_with_no_declared_region_is_a_no_op(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Detail\n\nNothing declared here.\n")

    changed, errors = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert (changed, errors) == (False, [])


def test_declared_block_report_mode_does_not_write(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Widget body.\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    original = f"# Detail\n\n{_declared_region('widget')}\n"
    target.write_text(original)

    changed, errors = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=False
    )
    assert changed is True
    assert errors and "differ" in errors[0]
    assert target.read_text() == original


# --- is_allowed_target: symlinked skill dirs (Task A's own self-adoption shape) -----


def test_is_allowed_target_follows_symlinked_skill_dir(tmp_path: Path) -> None:
    """This repo's own self-adoption layout: `skills/<name>/` is a symlink
    into `plugins/<family>/skills/<name>/`. `.resolve()` walks that symlink
    to its real location — outside the `skills/` root — and would reject
    every legitimate target here; `.absolute()` must not. This is the exact
    regression the `.resolve()` -> `.absolute()` fix exists to prevent, so
    it earns its own end-to-end test through `process_declared`, not just
    `is_allowed_target` in isolation."""
    real_dir = tmp_path / "real" / "demo"
    real_dir.mkdir(parents=True)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "demo").symlink_to(real_dir, target_is_directory=True)

    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Widget body text.\n")

    target = skills_dir / "demo" / "detail.md"
    target.write_text(f"# Detail\n\n{_declared_region('widget')}\n## Next\n")

    assert MOD.is_allowed_target(target, roots=(skills_dir,))

    changed, errors = MOD.process_declared(target, blocks_dir=blocks_dir, roots=(skills_dir,), fix=True)
    assert (changed, errors) == (True, [])
    assert "Widget body text." in target.read_text()
    # The write landed through the symlink, at the real file.
    assert "Widget body text." in (real_dir / "detail.md").read_text()


def test_is_allowed_target_rejects_dotdot_traversal(tmp_path: Path) -> None:
    """`.absolute()` alone does not collapse `..` segments, so a path like
    `skills/../docs/notes.md` would pass a naive `relative_to` prefix check
    even though it walks straight back out of `skills/`. `normpath` must
    close that gap."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (tmp_path / "docs").mkdir()

    traversal_path = skills_dir / ".." / "docs" / "notes.md"
    assert not MOD.is_allowed_target(traversal_path, roots=(skills_dir,))


# --- declared blocks: indentation is preserved, not just filled ---------------------


def test_declared_region_preserves_marker_indentation(tmp_path: Path) -> None:
    """A region nested under a list item (BEGIN/END indented 3 spaces, the
    `install.md` shape) must come back indented — not flush left, which
    would break the list it lives inside."""
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Line one.\n\nLine two.\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    region = (
        "   <!-- BEGIN MAGPIE BLOCK: widget — generated from tools/dev/blocks/widget.md -->\n"
        "   <!-- END MAGPIE BLOCK: widget -->\n"
    )
    target.write_text(f"2. Item.\n\n{region}\n3. Next.\n")

    new_text, errors = MOD.fill_declared(target.read_text(), blocks_dir=blocks_dir)
    assert errors == []
    lines = new_text.splitlines()
    assert any(line.startswith("   <!-- BEGIN MAGPIE BLOCK: widget") for line in lines)
    assert "   Line one." in lines
    assert "   Line two." in lines
    assert "   <!-- END MAGPIE BLOCK: widget -->" in lines


def test_declared_region_blank_lines_stay_truly_blank(tmp_path: Path) -> None:
    """Blank lines inside an indented region must never carry the indent as
    trailing whitespace — `trailing-whitespace` would strip it right back
    out on the next hook, and `--fix` would then report a change forever."""
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Line one.\n\nLine two.\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    region = (
        "   <!-- BEGIN MAGPIE BLOCK: widget — generated from tools/dev/blocks/widget.md -->\n"
        "   <!-- END MAGPIE BLOCK: widget -->\n"
    )
    target.write_text(f"2. Item.\n\n{region}\n")

    new_text, errors = MOD.fill_declared(target.read_text(), blocks_dir=blocks_dir)
    assert errors == []
    for line in new_text.splitlines():
        if line.strip() == "":
            assert line == "", f"blank line carries trailing whitespace: {line!r}"


def test_declared_region_indentation_is_idempotent(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("Line one.\n\nLine two.\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    region = (
        "   <!-- BEGIN MAGPIE BLOCK: widget — generated from tools/dev/blocks/widget.md -->\n"
        "   <!-- END MAGPIE BLOCK: widget -->\n"
    )
    target.write_text(f"2. Item.\n\n{region}\n3. Next.\n")

    changed, errors = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert (changed, errors) == (True, [])
    first = target.read_text()

    changed2, errors2 = MOD.process_declared(
        target, blocks_dir=blocks_dir, roots=(tmp_path / "skills",), fix=True
    )
    assert (changed2, errors2) == (False, [])
    assert target.read_text() == first


def test_declared_region_fence_near_indented_code_threshold(tmp_path: Path) -> None:
    """A 3-space-indented region containing a fenced code block sits one
    space shy of CommonMark's 4-space indented-code-block threshold — the
    fence must still render as a fence, not collapse into an indented code
    block, once the generator's own indent is added on top."""
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("```bash\necho hi\n```\n")

    target = tmp_path / "skills" / "demo" / "detail.md"
    target.parent.mkdir(parents=True)
    region = (
        "   <!-- BEGIN MAGPIE BLOCK: widget — generated from tools/dev/blocks/widget.md -->\n"
        "   <!-- END MAGPIE BLOCK: widget -->\n"
    )
    target.write_text(f"2. Item.\n\n{region}\n")

    new_text, errors = MOD.fill_declared(target.read_text(), blocks_dir=blocks_dir)
    assert errors == []
    assert "   ```bash" in new_text.splitlines()
    assert "   echo hi" in new_text.splitlines()
    assert "   ```" in new_text.splitlines()
    # Not 4+ spaces anywhere the fence content landed — that would be an
    # indented code block instead of a fenced one once rendered.
    assert "    echo hi" not in new_text


# --- strip_generated_regions: indented declared regions (skill-surface-hash.py) -----


def test_strip_generated_regions_strips_indented_declared_block() -> None:
    """`skill-surface-hash.py` calls this function directly to keep a
    declared block's contents out of a skill's reconciliation fingerprint.
    It must strip an *indented* region — indent on the BEGIN line included —
    exactly as cleanly as a flush-left one, or a nested block's text (and
    any heading inside it) leaks into the hashed surface."""
    text = (
        "1. Item.\n\n"
        "   <!-- BEGIN MAGPIE BLOCK: widget — generated from tools/dev/blocks/widget.md -->\n\n"
        "   Some generated text.\n\n"
        "   <!-- END MAGPIE BLOCK: widget -->\n\n"
        "2. Next.\n"
    )
    stripped = MOD.strip_generated_regions(text)
    assert "widget" not in stripped
    assert "Some generated text." not in stripped
    assert "1. Item." in stripped
    assert "2. Next." in stripped


# --- the pre-flight sidecar ---------------------------------------------------------
#
# The sidecar is the cold half of the pre-flight split: a whole generated file
# beside each non-exempt `SKILL.md`, carrying the branch handling the block
# points at. These tests pin the three properties the split depends on — the
# banner is present so nobody hand-edits a generated file, an exempt skill
# carries no sidecar, and writing is idempotent so the hook does not churn.


def test_detail_text_carries_the_banner_and_the_source_body(tmp_path: Path) -> None:
    module = _load()
    source = tmp_path / "preflight-detail.md"
    source.write_text("<!-- SPDX-License-Identifier: Apache-2.0 -->\n\n# Detail\n\nBody.\n")

    text = module.preflight_detail_text(source)

    assert text.startswith(module.PREFLIGHT_DETAIL_BANNER)
    assert "# Detail" in text and "Body." in text
    # Unlike the auto block, this is a standalone file: the repository's RAT
    # check scans it, so its own licence header has to survive.
    assert "SPDX-License-Identifier" in text


def test_detail_text_strips_a_leading_doctoc_region(tmp_path: Path) -> None:
    """A TOC for the source file is meaningless in a target that is not that
    file. One rode into all 65 copies before the source was excluded from the
    doctoc hook; stripping it here means a future source cannot repeat it."""
    module = _load()
    source = tmp_path / "preflight-detail.md"
    source.write_text(
        "<!-- START doctoc generated TOC please keep comment here -->\n"
        "- [Detail](#detail)\n"
        "<!-- END doctoc generated TOC please keep comment here -->\n"
        "\n<!-- SPDX-License-Identifier: Apache-2.0 -->\n\n# Detail\n\nBody.\n"
    )

    text = module.preflight_detail_text(source)

    assert "doctoc" not in text
    assert "# Detail" in text


def test_strip_licence_header_drops_a_doctoc_region_ahead_of_the_spdx_header() -> None:
    module = _load()
    raw = (
        "<!-- START doctoc generated TOC -->\n- [X](#x)\n<!-- END doctoc generated TOC -->\n"
        "\n<!-- SPDX-License-Identifier: Apache-2.0 -->\n\n## Heading\n"
    )
    assert module._strip_licence_header(raw) == "## Heading\n"


def test_apply_sidecar_writes_then_is_idempotent(tmp_path: Path) -> None:
    module = _load()
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: x\n---\n\n# X\n")

    assert module.apply_sidecar(skill, "content\n") is True
    assert (tmp_path / module.PREFLIGHT_DETAIL_NAME).read_text() == "content\n"
    # A second run with the same text must not report a change: the hook runs
    # with `--fix` on every commit, and a churning generator would rewrite 65
    # files each time.
    assert module.apply_sidecar(skill, "content\n") is False
    assert module.apply_sidecar(skill, "different\n") is True


def test_remove_sidecar_reports_whether_a_file_was_there(tmp_path: Path) -> None:
    module = _load()
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: x\n---\n\n# X\n")

    assert module.remove_sidecar(skill) is False
    module.apply_sidecar(skill, "content\n")
    assert module.remove_sidecar(skill) is True
    assert not (tmp_path / module.PREFLIGHT_DETAIL_NAME).exists()


def test_sidecar_state_distinguishes_missing_from_stale(tmp_path: Path) -> None:
    module = _load()
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: x\n---\n\n# X\n")

    assert "missing" in (module.sidecar_state(skill, "content\n") or "")
    module.apply_sidecar(skill, "old\n")
    assert "differs" in (module.sidecar_state(skill, "content\n") or "")
    module.apply_sidecar(skill, "content\n")
    assert module.sidecar_state(skill, "content\n") is None


def test_every_non_exempt_skill_carries_a_current_sidecar() -> None:
    """The live tree: each of the 65 propagated skills has the sidecar, byte
    for byte, and no `setup`-family skill has one at all."""
    module = _load()
    detail = module.preflight_detail_text(REPO / module.PREFLIGHT_DETAIL_SOURCE)

    carried, exempt = 0, 0
    for skill in sorted((REPO / "skills").glob("*/SKILL.md")):
        sidecar = skill.parent / module.PREFLIGHT_DETAIL_NAME
        if module.family_of(skill.read_text()) in module.EXEMPT_FAMILIES:
            assert not sidecar.exists(), f"{sidecar}: exempt skills carry no sidecar"
            exempt += 1
            continue
        assert sidecar.is_file(), f"{sidecar}: missing"
        assert sidecar.read_text() == detail, f"{sidecar}: differs from the source"
        carried += 1

    assert exempt == 10
    assert carried == 65
