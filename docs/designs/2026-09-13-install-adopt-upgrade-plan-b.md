<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Subsystem B — the marketplace install as a prerequisite: Implementation Plan](#subsystem-b--the-marketplace-install-as-a-prerequisite-implementation-plan)
  - [Global Constraints](#global-constraints)
  - [File Structure](#file-structure)
    - [Task 1: The prerequisite page](#task-1-the-prerequisite-page)
    - [Task 2: The quick start stops repeating it](#task-2-the-quick-start-stops-repeating-it)
    - [Task 3: The ten family READMEs](#task-3-the-ten-family-readmes)
    - [Task 4: Guard it](#task-4-guard-it)
  - [Self-review](#self-review)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Subsystem B — the marketplace install as a prerequisite: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Carry the marketplace install in exactly one place — a per-harness
prerequisite page — and have the quick start and the ten family READMEs point
at it instead of repeating it.

**Architecture:** Documentation only. No skill prose, no eval suites, no code
beyond one constant in `check-doc-sync.py`. The guard against regression is a
grep-shaped check: the `marketplace add` command may appear in the prerequisite
page and the marketplace reference, and nowhere else.

**Tech Stack:** Markdown; `tools/dev/check-doc-sync.py` (pure stdlib, already
hooked into prek); `prek` for doctoc / markdownlint / lychee.

**Spec:** [`2026-09-13-install-adopt-upgrade-design.md`](2026-09-13-install-adopt-upgrade-design.md) § Subsystem B

## Global Constraints

- **The family-specific install line stays.** `/plugin install
  magpie-<family>@apache-magpie` is not duplication — it differs per family.
  Only `/plugin marketplace add apache/magpie` is.
- **Two files may carry the marketplace add**, and no others:
  `docs/setup/marketplace-install.md` (the commands) and
  `docs/setup/marketplace.md` (the reference, where it is the subject).
- **Seven harnesses**, in the order the marketplace reference already uses:
  Claude Code, OpenAI Codex CLI, VS Code / GitHub Copilot, Google Gemini CLI,
  Cursor, `microsoft/apm`, JetBrains IDEs.
- **Do not restate per-harness caveats** the reference already carries
  (verification status, the per-family-is-Claude-Code-only constraint, the
  all-in-one token cost). The prerequisite page is commands; the reference is
  why.
- **Already shipped — do not redo:** the families sub-page, the two-modes
  reordering, Step 2b, and the four adoption mentions. See the design's amended
  B section.
- Every markdown file needs the SPDX header, doctoc markers, language tags on
  fenced code (MD040), and links that resolve (lychee runs on commit).
- Commit messages must end with `Generated-by: Claude Opus 5`. No
  `Co-Authored-By`.
- Signed commits fail in the sandbox with "Couldn't load public key" — that is
  the sandbox denying `~/.ssh`, not a missing key; retry with the sandbox
  disabled.

## File Structure

| File | Responsibility |
|---|---|
| `docs/setup/marketplace-install.md` (create) | The install commands, one section per harness, and nothing else |
| `docs/setup/marketplace.md` (modify) | Links to the new page for commands; keeps manifests, versioning, verification status |
| `docs/quick-start.md` (modify) | Step 1 becomes a prerequisite pointer; the teammates block becomes a top-level adopt step |
| `docs/*/README.md` × 10 (modify) | Drop the marketplace add; keep the one family install line; add the pointer |
| `tools/dev/check-doc-sync.py` (modify) | The eleventh check gains a twelfth sibling: the marketplace add appears only in the two allowed files |
| `tools/dev/tests/test_check_doc_sync.py` (modify) | Tests for that check |

---

### Task 1: The prerequisite page

**Files:**
- Create: `docs/setup/marketplace-install.md`
- Modify: `docs/setup/marketplace.md` — replace the command blocks with links

**Interfaces:**
- Produces: the page path and its per-harness anchors, which Tasks 2 and 3
  link to. Anchor slugs follow GitHub's rule — lowercase, spaces to hyphens,
  punctuation dropped, an em dash surrounded by spaces yielding a double
  hyphen.

- [ ] **Step 1: Collect the seven commands from the reference**

Read `docs/setup/marketplace.md`'s *Supported agents* section and copy each
harness's install commands verbatim. Do not invent or "improve" a command —
several were corrected upstream (`823241cf` fixed the Codex one), and the
reference is the source of truth.

- [ ] **Step 2: Write the page**

`docs/setup/marketplace-install.md`, with the SPDX header and doctoc markers.
Title: `# Prerequisite: install Magpie from your agent's marketplace`.

One `##` per harness, in the reference's order. Each section is a sentence of
context at most, then the commands. For Claude Code, the family install line is
shown as the pattern `/plugin install magpie-<family>@apache-magpie`, not a
specific family — the family pages carry their own.

Open with one short paragraph saying this is done once per machine, that it
writes nothing to any repository, and that everything else assumes it.

Close with a *Where to go next* list: the quick start, the marketplace
reference, and the prerequisites page for what individual skills need at run
time.

- [ ] **Step 3: Point the reference at it**

In `docs/setup/marketplace.md`, replace each per-harness command block with a
link to the new page's corresponding section. Keep every sentence that explains
*why* — manifests, per-family-vs-all-in-one, skill-name differences,
versioning, verification status. The reference loses commands, not reasoning.

- [ ] **Step 4: Verify**

```bash
prek run --all-files doctoc
prek run --all-files markdownlint-cli2
prek run --all-files lychee
```

Expected: all pass. lychee is the one that matters — it proves every anchor you
linked actually exists.

- [ ] **Step 5: Commit**

```bash
git add docs/setup/marketplace-install.md docs/setup/marketplace.md
git commit -m "docs(setup): carry the marketplace install in one page

The install commands lived in the marketplace reference, the quick start,
and all ten family READMEs. A one-time, per-machine prerequisite was being
re-explained as though it were part of every flow.

They now live once, one section per harness, in a page whose whole job is
the commands. The reference keeps the reasoning -- manifests, per-family
versus all-in-one, skill-name differences, versioning, verification
status -- and links for the commands.

Generated-by: Claude Opus 5"
```

---

### Task 2: The quick start stops repeating it

**Files:**
- Modify: `docs/quick-start.md`

**Interfaces:**
- Consumes: Task 1's page and anchors.
- Produces: the heading `## Step 3 — adopt it for your project`, which Task 3's
  family pointer does **not** reference (families link to the prerequisite, not
  to adoption).

- [ ] **Step 1: Replace Step 1's command blocks with a pointer**

`## Install from the Apache Magpie Marketplace` currently carries three
`marketplace add` blocks across four harness subsections. Replace the whole
section body with a short pointer to
`setup/marketplace-install.md`, keeping:

- the one-line statement of what installing does and does not touch;
- the `> [!IMPORTANT]` note about the all-in-one plugin's always-on cost;
- the `> [!TIP]` JetBrains note and the `> [!NOTE]` per-family-is-Claude-Code
  note **only if** they are not already on the new page. If they are, drop them
  here and link.

Retitle so the heading no longer promises commands the section no longer
carries. Check for inbound anchor references to
`#install-from-the-apache-magpie-marketplace` across the repo first and
rewrite them.

- [ ] **Step 2: Promote the teammates block to a step**

`#### Optional: adopt Magpie for your teammates` is a fourth-level heading
inside Step 1. Promote it to `## Adopt it for your project (optional)`, placed after
`## Lock the agent down` and before the families pointer, and
extend it with what the floor means — a minimum, never a ceiling, and what a
contributor gets on clone. Link `setup/team-adoption.md` for the full walk.

The walkthrough headings carry no step numbers, so nothing renumbers when a
section is added or moved. Keep it that way.

- [ ] **Step 3: Verify no marketplace add remains**

```bash
grep -n "plugin marketplace add apache/magpie" docs/quick-start.md
```

Expected: no output.

```bash
prek run --all-files doctoc && prek run --all-files lychee
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add docs/quick-start.md
git commit -m "docs: point the quick start at the install prerequisite

Step 1 carried the marketplace add for four harnesses inline, so a reader
who had already installed scrolled past it every time, and a reader who
had not met it three more times on the family pages.

It becomes a pointer, and the optional teammates block -- which is
adoption -- is promoted out of a fourth-level heading inside Step 1 into a
step of its own, with what the floor means.

Generated-by: Claude Opus 5"
```

---

### Task 3: The ten family READMEs

This is ten near-identical edits. Do them as **one batch**, not ten commits.

**Files:**
- Modify: `docs/security/README.md`, `docs/release-management/README.md`,
  `docs/pr-management/README.md`, `docs/issue-management/README.md`,
  `docs/repo-health/README.md`, `docs/contributor-growth/README.md`,
  `docs/utilities/README.md`, `docs/mentoring/README.md`,
  `docs/pairing/README.md`, `docs/setup/README.md`

**Interfaces:**
- Consumes: Task 1's page path.
- Produces: nothing consumed downstream. Subsystem C edits the same ten files
  in a different region (the intro and the screenshots), so **do not** reflow
  or re-wrap prose outside the install section — it makes C's diff unreadable.

- [ ] **Step 1: Establish the shape on one file**

In `docs/pairing/README.md`, the *Install & first runs* section currently reads:

````markdown
Install just this family — one plugin, 2 skills. …

```text
/plugin marketplace add apache/magpie
/plugin install magpie-pairing@apache-magpie
```
````

Change it to drop the first command and add a pointer above the block:

````markdown
Install just this family — one plugin, 2 skills. …

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-pairing@apache-magpie
```
````

Keep the skill count and the one-line pitch exactly as they are — the count is
checked by `check-doc-sync`'s family-README check, which keys on the install
command.

- [ ] **Step 2: Confirm the count check still passes on that one file**

```bash
python3 tools/dev/check-doc-sync.py
```

Expected: OK. This check reads the family from the `/plugin install
magpie-<family>@` line and the count from the prose above it — both survive.
If it fails, the pointer sentence has come between the count and the command;
move it above the count instead.

- [ ] **Step 3: Apply the same shape to the other nine**

Same edit, same wording, each with its own family name and skill count. `setup`
is `magpie-setup`; `issue-management`'s plugin is `magpie-issue`; check each
against its existing install line rather than deriving it from the directory
name.

- [ ] **Step 4: Verify**

```bash
grep -rn "plugin marketplace add apache/magpie" docs/ | grep -v "marketplace-install.md\|marketplace.md"
```

Expected: no output.

```bash
python3 tools/dev/check-doc-sync.py && prek run --all-files lychee
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add docs/
git commit -m "docs: family READMEs stop repeating the marketplace add

Ten pages carried the same two-line block, of which only the second line
differed. The marketplace add is a one-time prerequisite; the family
install is the page's actual subject.

Each README now points at the prerequisite and shows only its own install
line.

Generated-by: Claude Opus 5"
```

---

### Task 4: Guard it

Without this, the repetition returns the next time someone documents an
install, and nothing notices.

**Files:**
- Modify: `tools/dev/check-doc-sync.py`
- Modify: `tools/dev/tests/test_check_doc_sync.py`
- Modify: `tools/dev/README.md` — the table cell describing the script

**Interfaces:**
- Consumes: the two-file allowlist from Global Constraints.
- Produces: nothing downstream.

- [ ] **Step 1: Write the failing test**

In `tools/dev/tests/test_check_doc_sync.py`, following the existing fixture
style (`repo` fixture, `_errors` helper):

```python
def test_marketplace_add_outside_the_allowed_pages_is_reported(repo: Path) -> None:
    (repo / "docs" / "setup").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "setup" / "marketplace-install.md").write_text(
        "/plugin marketplace add apache/magpie\n", encoding="utf-8"
    )
    (repo / "docs" / "pairing").mkdir(parents=True)
    (repo / "docs" / "pairing" / "README.md").write_text(
        "```text\n/plugin marketplace add apache/magpie\n```\n", encoding="utf-8"
    )
    errs = _errors(mod.check_marketplace_add_is_not_repeated)
    assert len(errs) == 1
    assert "docs/pairing/README.md" in errs[0]


def test_marketplace_add_in_the_allowed_pages_is_silent(repo: Path) -> None:
    setup = repo / "docs" / "setup"
    setup.mkdir(parents=True, exist_ok=True)
    for name in ("marketplace-install.md", "marketplace.md"):
        (setup / name).write_text("/plugin marketplace add apache/magpie\n", encoding="utf-8")
    assert _errors(mod.check_marketplace_add_is_not_repeated) == []
```

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run --project tools/dev --group dev pytest tools/dev/tests/test_check_doc_sync.py -q -k marketplace_add
```

Expected: FAIL — `module has no attribute 'check_marketplace_add_is_not_repeated'`.

- [ ] **Step 3: Implement the check**

```python
MARKETPLACE_ADD_ALLOWED = (
    Path("docs/setup/marketplace-install.md"),
    Path("docs/setup/marketplace.md"),
)
_MARKETPLACE_ADD = re.compile(r"plugin marketplace add apache/magpie")


def check_marketplace_add_is_not_repeated(errors: list[str]) -> None:
    """The one-time prerequisite belongs on one page.

    It was carried by the marketplace reference, the quick start and all ten
    family READMEs, so a reader met it four times before installing anything
    and a maintainer had twelve copies to keep correct.
    """
    for md in sorted(Path("docs").rglob("*.md")):
        if md in MARKETPLACE_ADD_ALLOWED:
            continue
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if _MARKETPLACE_ADD.search(line):
                errors.append(
                    f"{md}:{lineno}: the marketplace add belongs on "
                    f"{MARKETPLACE_ADD_ALLOWED[0]}; link to it instead of repeating it"
                )
```

Call it from `main()` alongside the others, and add it to the module
docstring's numbered list as check twelve.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run --project tools/dev --group dev pytest tools/dev/tests/test_check_doc_sync.py -q
python3 tools/dev/check-doc-sync.py
```

Expected: all tests pass, and the real repo is clean — which it will be only
if Tasks 1–3 landed. If the check fires on a file Tasks 1–3 were supposed to
clear, that is a real miss: fix the file, not the allowlist.

- [ ] **Step 5: Document and commit**

Update the `check-doc-sync.py` row in `tools/dev/README.md` to name the new
check.

```bash
uv run --project tools/dev --group dev ruff format tools/dev/
git add tools/dev/
git commit -m "feat(dev): keep the marketplace add on one page

Twelve copies of a one-time prerequisite is what the previous state looked
like, and nothing would have noticed a thirteenth.

check-doc-sync gains a twelfth check: the marketplace add may appear in
the prerequisite page and the marketplace reference, and nowhere else
under docs/.

Generated-by: Claude Opus 5"
```

---

## Self-review

**Spec coverage.** The design's amended B table has five remaining rows: the
prerequisite page (Task 1), the reference linking to it (Task 1), the
quick-start pointer (Task 2), the teammates block becoming a step (Task 2), and
the ten family READMEs (Task 3). Task 4 is not in the design; it is added
because the design's central claim — that the install is carried once — has no
guard otherwise, and this repository has now twice had a documented fact drift
because nothing checked it.

**Type consistency.** `check_marketplace_add_is_not_repeated` is named
identically in the test, the implementation and the `main()` call. The
allowlist constant is the same tuple in the constraint list, the implementation
and the tests.

**Known risk.** Task 2's renumbering may break inbound anchors; the task
requires checking before choosing a scheme rather than after. Task 3 warns
against reflowing prose because Subsystem C edits the same ten files.
