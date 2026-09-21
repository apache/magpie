<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Reconciliation tracking implementation plan](#reconciliation-tracking-implementation-plan)
  - [Global Constraints](#global-constraints)
    - [Task 1: The surface-hash generator](#task-1-the-surface-hash-generator)
    - [Task 2: The validator requires the field](#task-2-the-validator-requires-the-field)
    - [Task 3: The `reconciled:` block in the lock format](#task-3-the-reconciled-block-in-the-lock-format)
    - [Task 4: The pre-flight check](#task-4-the-pre-flight-check)
    - [Task 5: `setup reconcile`](#task-5-setup-reconcile)
    - [Task 6: `verify` sweeps, compares, and is suggested](#task-6-verify-sweeps-compares-and-is-suggested)
    - [Task 7: `config` and `adopt` write the stamp](#task-7-config-and-adopt-write-the-stamp)
    - [Task 8: Specs, the config key, and the whole-tree gate](#task-8-specs-the-config-key-and-the-whole-tree-gate)
  - [Self-review notes](#self-review-notes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Reconciliation tracking implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give marketplace installs the reconciliation half the snapshot
methods already have — a stamp of what `setup` last reconciled, a free
per-skill check against it in pre-flight, and a sweep that resolves the
unstamped case once.

**Architecture:** One deterministic generator writes a `surface_hash:`
frontmatter field into every skill, computed from the two things
reconciliation cares about (`requires_config` and structural anchors). Every
other moving part is agentic prose: the shared pre-flight block compares its
own hash against a `reconciled:` stamp in the lock, and the `setup` family
writes that stamp, sweeps, and reports.

**Tech Stack:** Python 3.13 stdlib (`hashlib`, `re`, `argparse`), pytest,
prek hooks, Magpie skill markdown, `tools/skill-evals` fixtures.

**Spec:** [`2026-09-21-marketplace-reconciliation-tracking.md`](2026-09-21-marketplace-reconciliation-tracking.md)

**Lifecycle:** This plan is deleted when the work lands, per
[`docs/designs/README.md`](README.md) — the design stays, the task list does
not. It is deliberately absent from that file's index table, which lists
designs.

## Global Constraints

- **Commit trailer:** every commit ends with `Generated-by: <agent name and
  version>`. `Co-Authored-By:` is blocked by the agent-guard hook.
- **Never bypass hooks.** `prek run --all-files` before pushing; no
  `--no-verify`.
- **Skills stay project-agnostic.** Use the placeholders from `AGENTS.md`;
  `tools/dev/check-placeholders.sh` is the gate.
- **Semantic line breaks** (one sentence per line) in all prose.
- **Generated fields are never hand-edited** — `surface_hash:` is written
  only by its generator, like the figures in `docs/mode-economics.md`.
- **Every skill or prompt-material change** re-runs that skill's eval suite
  and, where the token shape moves, `docs/mode-economics.md`
  (`uv run --project tools/skill-token-count skill-token-count --write`).
- **PEP 440 comparison everywhere, dev segment included.** No code or prose
  strips `.devN`.

---

### Task 1: The surface-hash generator

**Files:**
- Create: `tools/dev/skill-surface-hash.py`
- Create: `tools/dev/tests/test_skill_surface_hash.py`
- Modify: `.pre-commit-config.yaml` (new `skill-surface-hash` hook, placed
  immediately **after** `check-skill-preflight` and **before**
  `skill-token-count`, so it hashes the post-propagation file and the token
  count measures the post-hash file)

**Interfaces:**
- Consumes: nothing.
- Produces: `surface_inputs(text: str) -> tuple[list[str], list[str]]`
  returning `(requires_config, anchors)`; `surface_hash(text: str) -> str`
  returning `"sha256:"` plus the first 16 hex characters; `apply(path:
  Path, digest: str) -> tuple[bool, str | None]` returning `(changed,
  error)`, mirroring `check-skill-preflight.py`'s `apply`.

- [ ] **Step 1: Write the failing tests**

```python
# tools/dev/tests/test_skill_surface_hash.py  (ASF licence header first,
# copied verbatim from tools/dev/tests/test_check_family_plugins.py)
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

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
    reworded = SKILL.replace(
        "Some prose that may be reworded freely.", "Entirely different prose here."
    )
    assert MOD.surface_hash(reworded) == MOD.surface_hash(SKILL)


def test_renamed_heading_moves_the_hash() -> None:
    renamed = SKILL.replace("## Step 1 — gather", "## Step 1 — collect")
    assert MOD.surface_hash(renamed) != MOD.surface_hash(SKILL)


def test_changed_requires_config_moves_the_hash() -> None:
    changed = SKILL.replace("  - demo.md\n", "  - demo.md\n  - extra.md\n")
    assert MOD.surface_hash(changed) != MOD.surface_hash(SKILL)


def test_requires_config_order_does_not_matter() -> None:
    reordered = SKILL.replace(
        "  - project.md\n  - demo.md\n", "  - demo.md\n  - project.md\n"
    )
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --project tools/dev pytest tools/dev/tests/test_skill_surface_hash.py -v`
Expected: collection error — `skill-surface-hash.py` does not exist.

- [ ] **Step 3: Write the generator**

Model it on `tools/dev/check-skill-preflight.py`, which it sits beside: same
ASF header, a module docstring explaining *why* the hash exists (a running
skill must know whether its own surface moved since the project was
reconciled, and it cannot hash itself at runtime), the same
`SKILLS = Path("skills")` glob, the same `--fix` / report-and-fail split,
and the same exit codes.

```python
SKILLS = Path("skills")

BEGIN = "<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->"
END = "<!-- END MAGPIE PREFLIGHT -->"
PREFLIGHT_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
REQUIRES_RE = re.compile(r"^requires_config:\n((?:[ \t]+-[ \t]*\S+\n)+)", re.M)
ITEM_RE = re.compile(r"^[ \t]+-[ \t]*(\S+)[ \t]*$", re.M)
HEADING_RE = re.compile(r"^#{2,3}[ \t]+(.+?)[ \t]*$", re.M)
GOLDEN_RE = re.compile(r"^\*\*(Golden rule[^*]+)\*\*", re.M)
HASH_RE = re.compile(r"^surface_hash:[ \t]*\S+\n", re.M)


def _normalise(text: str) -> str:
    """Anchor text without markdown decoration, so `**Step 1**` == `Step 1`."""
    text = re.sub(r"[`*_]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def surface_inputs(text: str) -> tuple[list[str], list[str]]:
    front = FRONTMATTER_RE.match(text)
    body = text[front.end():] if front else text
    body = PREFLIGHT_RE.sub("", body)

    requires: list[str] = []
    block = REQUIRES_RE.search(front.group(1) + "\n") if front else None
    if block:
        requires = sorted(ITEM_RE.findall(block.group(1)))

    anchors = sorted(
        {_normalise(m) for m in HEADING_RE.findall(body)}
        | {_normalise(m) for m in GOLDEN_RE.findall(body)}
    )
    return requires, anchors


def surface_hash(text: str) -> str:
    requires, anchors = surface_inputs(text)
    payload = "\n".join(["requires_config:", *requires, "anchors:", *anchors])
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]
```

`apply()` removes any existing `surface_hash:` line from the frontmatter and
re-inserts it immediately **before** the `license:` line (a stable position,
and `license:` is required on every skill), rewriting only when the text
differs. `main()` takes `--fix`, iterates `sorted(SKILLS.glob("*/SKILL.md"))`,
and — unlike the pre-flight hook — exempts nothing: the `setup` family needs
a hash like every other skill, because `setup`'s own configuration can go
stale too.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --project tools/dev pytest tools/dev/tests/test_skill_surface_hash.py -v`
Expected: all pass except `test_every_live_skill_is_current`, which fails
until Step 6.

- [ ] **Step 5: Wire the hook**

```yaml
  # The reconciliation fingerprint. Runs after the pre-flight propagation so
  # it hashes the file an adopter actually installs, and before the token
  # count so that measurement sees the final bytes. The hash covers only
  # `requires_config` and the skill's structural anchors: a reworded
  # paragraph must not tell every adopter their configuration went stale,
  # and a renamed step must.
  - repo: local
    hooks:
      - id: skill-surface-hash
        name: skill-surface-hash (reconciliation fingerprint in every SKILL.md)
        language: system
        entry: python3 tools/dev/skill-surface-hash.py --fix
        files: ^(skills/[^/]+/SKILL\.md|plugins/magpie-[^/]+/skills/[^/]+/SKILL\.md)$
        pass_filenames: false
```

- [ ] **Step 6: Generate the field across every skill, as its own commit**

Run: `python3 tools/dev/skill-surface-hash.py --fix`
Then: `uv run --project tools/dev pytest tools/dev/tests/test_skill_surface_hash.py -v` (all pass)
Then: `uv run --project tools/skill-token-count skill-token-count --write`

- [ ] **Step 7: Commit — generator and hook separately from the bulk diff**

```bash
git add tools/dev/skill-surface-hash.py tools/dev/tests/test_skill_surface_hash.py .pre-commit-config.yaml
git commit -m "feat(dev): generate a reconciliation fingerprint for every skill

Generated-by: <agent name and version>"
git add skills plugins docs/mode-economics.md
git commit -m "chore(skills): add the generated surface_hash field

Generated-by: <agent name and version>"
```

---

### Task 2: The validator requires the field

**Files:**
- Modify: `tools/skill-and-tool-validator/src/skill_and_tool_validator/__init__.py`
- Test: `tools/skill-and-tool-validator/tests/test_validator.py`

**Interfaces:**
- Consumes: the `surface_hash:` field from Task 1.
- Produces: a hard validation failure when a `SKILL.md` lacks
  `surface_hash:` or carries one that is not `sha256:` + 16 hex characters.

- [ ] **Step 1: Write the failing test**

```python
def test_missing_surface_hash_is_an_error(tmp_path: Path) -> None:
    skill = _write_minimal_skill(tmp_path)            # existing test helper
    skill.write_text(skill.read_text().replace("surface_hash: sha256:0123456789abcdef\n", ""))
    errors = check_skill(skill)
    assert any("surface_hash" in e for e in errors)


def test_malformed_surface_hash_is_an_error(tmp_path: Path) -> None:
    skill = _write_minimal_skill(tmp_path)
    skill.write_text(skill.read_text().replace("sha256:0123456789abcdef", "deadbeef"))
    errors = check_skill(skill)
    assert any("surface_hash" in e for e in errors)
```

Add `surface_hash: sha256:0123456789abcdef` to whatever minimal-skill
fixture the existing tests build, so every other test keeps passing.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project tools/skill-and-tool-validator pytest tools/skill-and-tool-validator/tests/test_validator.py -k surface_hash -v`
Expected: FAIL — no error is raised.

- [ ] **Step 3: Implement the check**

Beside the existing `license:` check, with the same error wording style, and
a comment recording that the field is generated: the fix is to run the hook,
never to type a value.

- [ ] **Step 4: Run to verify they pass, then the whole suite**

Run: `uv run --project tools/skill-and-tool-validator pytest tools/skill-and-tool-validator/tests/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/skill-and-tool-validator
git commit -m "feat(validator): require the generated surface_hash on every skill

Generated-by: <agent name and version>"
```

---

### Task 3: The `reconciled:` block in the lock format

**Files:**
- Modify: `plugins/magpie-setup/skills/setup/locks.md`
- Modify: `docs/setup/agentic-overrides.md` (the *Reconciliation on framework
  upgrade* section gains the marketplace half)

**Interfaces:**
- Produces: the stamp format every later task reads and writes —
  `reconciled:` with `version:`, `at:`, and `skills:` mapping
  `<plugin>/<skill>` to a `sha256:…` value; plus the local-only keys
  `verified_at`, `verify_suggested_at` and `acknowledged` in
  `.apache-magpie-local/reconciled.json`.

- [ ] **Step 1: Document the block in `locks.md`**

Add a section after *`method: marketplace` — the adoption floor* that states,
with the worked example from the design: what each key means; that the block
is written only by `setup`; that an adopted project carries it in
`.apache-magpie.lock` while a configured-but-unadopted one carries the same
shape in `.apache-magpie-local/reconciled.json`; and that `verified_at`,
`verify_suggested_at` and `acknowledged` are **always** local, never
committed, because running `verify` and declining a prompt are per-machine
acts and a committed timestamp would dirty every contributor's tree.

- [ ] **Step 2: Document the marketplace half of reconciliation**

In `docs/setup/agentic-overrides.md`, extend *Reconciliation on framework
upgrade* to say that snapshot adopters reach it through
`/magpie-setup upgrade` and marketplace adopters through the stamp — the
per-skill comparison in pre-flight, and `/magpie-setup reconcile` for the
sweep. Same two ⚠ outcomes as today; only the trigger differs.

- [ ] **Step 3: Verify the links and anchors**

Run: `prek run lychee --all-files`
Expected: PASS — in particular no `Fragment not found` for the new anchors.

- [ ] **Step 4: Commit**

```bash
git add plugins/magpie-setup/skills/setup/locks.md docs/setup/agentic-overrides.md
git commit -m "docs(setup): specify the reconciled stamp and its marketplace flow

Generated-by: <agent name and version>"
```

---

### Task 4: The pre-flight check

**Files:**
- Modify: `tools/dev/preflight-block.md`
- Modify: every `SKILL.md` (generated — via `--fix`, never by hand)
- Create: `tools/skill-evals/evals/preflight-reconciliation/` with
  `README.md` and a `step-reconciliation/fixtures/` directory containing
  `step-config.json`, `user-prompt-template.md`, `output-spec.md`, and one
  directory per case holding `report.md` + `expected.json`

**Interfaces:**
- Consumes: `surface_hash` (Task 1), the stamp format (Task 3).
- Produces: the four pre-flight outcomes every later task refers to —
  `silent`, `propose_config`, `propose_reanchor`, `propose_sweep`.

- [ ] **Step 1: Write the eval fixtures first**

`step-config.json`:

```json
{
  "skill_md": "tools/dev/preflight-block.md",
  "step_heading": "## Pre-flight — is this project set up?"
}
```

`output-spec.md` requires exactly:

```json
{"outcome": "silent | propose_config | propose_reanchor | propose_sweep",
 "changed": ["<what moved, empty when silent>"],
 "update_available": "<version or null>"}
```

Five cases, each a `report.md` stating the machine's state and an
`expected.json`:

| Case | State | `outcome` |
|---|---|---|
| `case-1-in-sync` | stamp hash == skill hash | `silent` |
| `case-2-config-moved` | hashes differ, `requires_config` gained an entry | `propose_config` |
| `case-3-anchor-moved` | hashes differ, a step heading was renamed | `propose_reanchor` |
| `case-4-no-stamp` | lock has no `reconciled:` block | `propose_sweep` |
| `case-5-declined` | hashes differ, local `acknowledged` == current hash | `silent` |

Case 2 also sets a readable marketplace clone one dev build ahead, and its
`expected.json` carries that version in `update_available` — the piggybacked
report. Case 1 sets the same clone state and expects `update_available: null`,
pinning the rule that a silent reconciliation check says nothing about
updates.

- [ ] **Step 2: Run the suite to watch it fail**

Run: `PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner tools/skill-evals/evals/preflight-reconciliation/`
Expected: the extracted prompt contains no reconciliation instructions, so
the model cannot produce the required shape.

- [ ] **Step 3: Write the block**

In `tools/dev/preflight-block.md`, after the existing step 3 and before
"Unless step 3 passed silently, stop", add the comparison: read own
`surface_hash` from own frontmatter; read own entry from `reconciled.skills`
in the lock (or the local file); equal → silent; different → name whether
`requires_config` or an anchor moved and propose the matching fix; missing
entry → propose the sweep of *When nothing is stamped*, once, remembering a
decline in `acknowledged`.

Two fixes to the existing text go in the same edit:

- step 3 currently treats an empty `claude plugin list --json` as *no plugin
  installed*. In a sandboxed session the plugin cache is read-denied and the
  call returns `[]`, so the block must treat an unreadable plugin manager as
  **unknown** — run nothing, say nothing — never as absent;
- the version comparison paragraph gains the explicit statement that a dev
  build is a version like any other, and that the reconciliation prompt is
  gated on the fingerprint while `verify` reports every delta.

And the end-of-run item: suggest `/magpie-setup verify` when
`verified_at` (else the stamp's `at:`) is older than
`setup.verify_interval_days` (default 14, `0` disables), writing
`verify_suggested_at` when shown, next to the existing step 8.

- [ ] **Step 4: Propagate and re-measure**

Run: `python3 tools/dev/check-skill-preflight.py --fix`
Then: `python3 tools/dev/skill-surface-hash.py --fix`
Then: `uv run --project tools/skill-token-count skill-token-count --write`

Note: the pre-flight region is excluded from the hash, so this must produce
**no** `surface_hash` change. If it does, Task 1's exclusion is wrong — stop
and fix it there.

- [ ] **Step 5: Run the eval suite to verify it passes**

Run: `PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner tools/skill-evals/evals/preflight-reconciliation/`
Expected: all five cases produce the expected JSON.

- [ ] **Step 6: Commit**

```bash
git add tools/dev/preflight-block.md skills plugins tools/skill-evals/evals/preflight-reconciliation docs/mode-economics.md
git commit -m "feat(setup): compare each skill against the reconciliation stamp in pre-flight

Generated-by: <agent name and version>"
```

---

### Task 5: `setup reconcile`

**Files:**
- Create: `plugins/magpie-setup/skills/setup/reconcile.md`
- Modify: `plugins/magpie-setup/skills/setup/SKILL.md` (sub-action routing,
  the description block, and `argument-hint`)
- Create: `tools/skill-evals/evals/setup/step-reconcile/fixtures/` with the
  same four files plus cases

**Interfaces:**
- Consumes: the stamp format (Task 3), the pre-flight outcomes (Task 4).
- Produces: the sweep contract `verify` reuses read-only in Task 6.

- [ ] **Step 1: Write `reconcile.md`**

Follow the shape of the sibling sub-action pages (`upgrade.md` is the
closest: it also walks overrides). It documents: enumerate every configured
skill (`requires_config` resolution) and every override file; for each,
check that the anchors it names still exist in the skill it targets and that
its config resolves; propose the re-anchoring and config fixes as a numbered
list the user confirms item by item; on confirmation, apply and rewrite the
stamp; on decline, write `acknowledged` and change nothing else.

State the sandbox degradation plainly: resolving another skill's anchors
needs the plugin cache, which a sandboxed session cannot read, so there the
sweep covers the repository side and says what it could not check rather
than reporting a clean sweep it did not perform.

State the baseline rule: the sweep validates the present and needs no
baseline; the guessed one — lock `min_version`, else the last commit
touching `.apache-magpie.lock` or `.apache-magpie-overrides/` mapped through
the marketplace clone's history, else `.apache-magpie-local/` mtimes, else
nothing — only shapes the wording, and is phrased as an estimate.

- [ ] **Step 2: Add the eval cases**

`step-config.json` points at `plugins/magpie-setup/skills/setup/reconcile.md`
with `"step_heading": "## The sweep"`. Three cases: a clean sweep (stamp
written, nothing proposed); a stale anchor (one re-anchor proposed, naming
the override file and the heading that moved); a sandboxed run (partial
result, `"unchecked": ["anchor-resolution"]`).

- [ ] **Step 3: Run the suite**

Run: `PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner tools/skill-evals/evals/setup/`
Expected: the three new cases pass alongside the existing ones.

- [ ] **Step 4: Regenerate and commit**

```bash
python3 tools/dev/skill-surface-hash.py --fix
uv run --project tools/skill-token-count skill-token-count --write
git add plugins/magpie-setup docs/mode-economics.md tools/skill-evals/evals/setup skills
git commit -m "feat(setup): add the reconcile sub-action

Generated-by: <agent name and version>"
```

---

### Task 6: `verify` sweeps, compares, and is suggested

**Files:**
- Modify: `plugins/magpie-setup/skills/setup/verify.md`
- Modify: `plugins/magpie-setup/skills/setup/SKILL.md` (verify's summary line)
- Modify: `tools/skill-evals/evals/setup/step-verify/fixtures/` (new cases;
  create the step directory if the suite has none)

**Interfaces:**
- Consumes: Task 5's sweep contract, Task 3's local keys.
- Produces: `verified_at`, written on every completed verify run.

- [ ] **Step 1: Extend `verify.md`**

Three additions: run Task 5's sweep read-only and report it; read the
marketplace clone (`~/.claude/plugins/marketplaces/<name>`, resolved from
`claude plugin marketplace list --json`) and report every installed plugin
whose version is behind it, comparing as PEP 440 **including** the dev
segment, so a newer dev build is reported as the update it is; write
`verified_at` on completion.

Say why this surface owns the comparison: it is the only one that runs
deliberately and unsandboxed often enough to read the clone, and an
unreadable clone is reported as "could not check", never as "up to date".

- [ ] **Step 2: Add the eval cases**

Two: a dev-to-dev delta (`update_available` carries the newer dev version —
this is the case that pins decision 7); an unreadable clone
(`update_available: null` **and** an explicit `"unchecked":
["latest-version"]`, distinguishing *nothing newer* from *could not look*).

- [ ] **Step 3: Run the suite, regenerate, commit**

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner tools/skill-evals/evals/setup/
python3 tools/dev/skill-surface-hash.py --fix
uv run --project tools/skill-token-count skill-token-count --write
git add plugins/magpie-setup tools/skill-evals/evals/setup skills docs/mode-economics.md
git commit -m "feat(setup): verify sweeps reconciliation and reports newer plugin versions

Generated-by: <agent name and version>"
```

---

### Task 7: `config` and `adopt` write the stamp

**Files:**
- Modify: `plugins/magpie-setup/skills/setup/config.md`
- Modify: `plugins/magpie-setup/skills/setup/adopt.md`
- Modify: `tools/skill-evals/evals/setup/` (one case per sub-action)

**Interfaces:**
- Consumes: the stamp format (Task 3).
- Produces: the stamp that makes Task 4's check meaningful.

- [ ] **Step 1: Extend `config.md`**

After it writes `.apache-magpie-local/<file>`, it records the entries for the
skills it configured: each skill's current `surface_hash`, the plugin version
from the skill's base-directory path, and today's date — into the committed
lock when the project is adopted, else into
`.apache-magpie-local/reconciled.json`. Unchanged: it writes nothing outside
those gitignored paths unless the project is already adopted.

- [ ] **Step 2: Extend `adopt.md`**

Adoption writes the `reconciled:` block into `.apache-magpie.lock` alongside
the floor, covering every skill the project configures or overrides at that
moment. Note that this is the one path where the stamp enters git, and it
enters as part of a commit the maintainer is already making deliberately.

- [ ] **Step 3: Add one eval case per sub-action**

`config` on an adopted project → stamp entries in the lock; `config` on an
unadopted one → the same entries in the local file, lock untouched.

- [ ] **Step 4: Run the suite, regenerate, commit**

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner tools/skill-evals/evals/setup/
python3 tools/dev/skill-surface-hash.py --fix
uv run --project tools/skill-token-count skill-token-count --write
git add plugins/magpie-setup tools/skill-evals/evals/setup skills docs/mode-economics.md
git commit -m "feat(setup): config and adopt record what they reconciled

Generated-by: <agent name and version>"
```

---

### Task 8: Specs, the config key, and the whole-tree gate

**Files:**
- Modify: `tools/spec-loop/specs/adoption-and-setup.md`
- Modify: `tools/spec-loop/specs/marketplace-distribution.md`
- Modify: `docs/mode-economics.md` (prose, if the per-invocation shape moved)
- Modify: `AGENTS.md` only if the configuration-resolution section needs the
  new key named

**Interfaces:**
- Consumes: everything above.
- Produces: the durable statement of what shipped.

- [ ] **Step 1: Add the acceptance criteria**

In `adoption-and-setup.md`, add criteria covering: the stamp exists and is
written only by `setup`; adopted projects commit it, configured-but-unadopted
ones keep it local; a skill whose surface moved since the stamp says so and
proposes the fix; an unstamped project is offered one sweep, not silence; a
declined proposal does not return until the surface moves. In
`marketplace-distribution.md`, add: a marketplace install gets the same
reconciliation guarantee as a snapshot install, by a different route; and
version comparison includes the dev segment.

- [ ] **Step 2: Document `setup.verify_interval_days`**

Wherever the config-resolution chain lists keys, with its default of 14, `0`
to disable, and its resolution order project → organization → framework.

- [ ] **Step 3: Sync the spec marker**

Per `AGENTS.md`, confirm `tools/spec-loop/.last-sync` is at or near the
current `main` tip, and bump it in this PR if the only gap is this work.

- [ ] **Step 4: Whole-tree gate**

Run: `prek run --all-files`
Expected: 32 hooks, exit 0. `skill-surface-hash`, `skill-token-count`,
`spec-validate`, `check-doc-sync` and `lychee` are the ones most likely to
have something to say.

- [ ] **Step 5: Commit and open the PR**

```bash
git add tools/spec-loop docs AGENTS.md
git commit -m "docs(specs): state the reconciliation guarantee for marketplace installs

Generated-by: <agent name and version>"
gh pr create --repo apache/magpie --base main --web \
  --title "feat(setup): reconciliation tracking for marketplace installs" \
  --body-file <(printf '%s' "$PR_BODY")
```

The PR body follows `.github/PULL_REQUEST_TEMPLATE.md`, links the design,
and names the bulk `surface_hash` commit as mechanical so the reviewer skips
it.

---

## Self-review notes

**Spec coverage.** Stamp shape → Task 3. Fingerprint definition and
generation → Tasks 1–2. Pre-flight self-check, the unknown-vs-absent fix,
and the dev-version rule → Task 4. The unstamped sweep → Tasks 4 (proposal)
and 5 (execution). Who writes the stamp → Tasks 5–7. Latest-version
comparison and the fortnightly nudge → Tasks 4 (the nudge) and 6 (the
comparison). Specs → Task 8. No section of the design is unimplemented.

**Ordering.** Tasks 1–3 are independent of each other; 4 needs 1 and 3; 5
needs 4; 6 and 7 need 5; 8 needs all. A reviewer can reject any one without
unpicking its neighbours, except that 4 is meaningless before 1 lands.

**Known risk carried from the design.** The anchor definition in Task 1
(`##`/`###` headings plus `**Golden rule …**` lines) is the judgement call.
If prompts turn out unactionable in practice, that regex — and only that
regex — is what changes.
