<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Subsystem C — family intros: Implementation Plan](#subsystem-c--family-intros-implementation-plan)
  - [Global Constraints](#global-constraints)
  - [File Structure](#file-structure)
    - [Task 1: The renderer](#task-1-the-renderer)
    - [Task 2: Twenty-two transcripts](#task-2-twenty-two-transcripts)
    - [Task 3: Callouts, and the recordings retired](#task-3-callouts-and-the-recordings-retired)
    - [Task 4: Rework the checker](#task-4-rework-the-checker)
    - [Task 5: Re-cut the setup recording](#task-5-re-cut-the-setup-recording)
  - [Self-review](#self-review)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Subsystem C — family intros: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each of the ten family READMEs a coloured benefit callout and
two or three authored screenshots of that family actually working, and retire
the nine recordings that all showed the same thing.

**Architecture:** A generator plus authored inputs. Each screenshot is a
committed `.txt` transcript rendered to a static `.svg` by a new
`tools/dev/render-screenshot.sh`. Rendering is deterministic, so the checker
can assert every `.svg` still regenerates byte-identically from its `.txt` —
the staleness guard hand-authored SVGs cannot have. `record-svg.sh` survives
for the one real recording.

**Tech Stack:** Bash (the renderer); Python stdlib (`check-quickstart-recording.py`);
Markdown; `prek` for doctoc / markdownlint / lychee. **No Node, no npx** — the
existing recorder shells out to `svg-term-cli` via npx, and this renderer
deliberately does not, because it must run in CI and on a contributor's machine
without a Node install.

**Spec:** [`2026-09-13-install-adopt-upgrade-design.md`](2026-09-13-install-adopt-upgrade-design.md) § Subsystem C

## Global Constraints

- **Screenshots are authored, not captured.** The `.txt` is written by hand to
  show a typical run. It is not a transcript of a real session and must not be
  presented as one.
- **Deterministic rendering.** Same `.txt`, same `.svg`, byte for byte. No
  timestamps, no random ids, no embedded generation date.
- **No Node.** The renderer emits SVG directly from Bash; `svg-term-cli` is the
  recorder's dependency, not this one.
- **Ten families, but nine recordings** — `setup` has none, because its first
  run *is* `magpie-setup.svg`. Every per-family rule in this plan is about the
  nine; `setup` gets a callout and screenshots like the rest, but has no
  recording to retire.
- **Transcripts must be robust to cosmetic change.** No version strings, no
  counts a minor change would move, no dates. The checker can prove an `.svg`
  matches its `.txt`; nothing can prove the `.txt` matches what the skill
  prints today, and that gap is the accepted cost of not re-capturing.
- **Nothing secret in frame.** These files are text and greppable forever. No
  tokens, no private repo names, no reporter addresses. For `security`,
  invented issue numbers and a scratch tracker name only.
- **`> [!TIP]` for the callout** — the only coloured notice that renders as one
  on GitHub and degrades to a readable blockquote everywhere else.
- **Do not reflow prose** in the ten READMEs outside the regions this plan
  names. Subsystem B edits their install sections.
- Every markdown file needs the SPDX header and doctoc markers; every generated
  SVG carries the Apache licence header.
- Commit messages end with `Generated-by: Claude Opus 5`. No `Co-Authored-By`.
- Signed commits fail in the sandbox with "Couldn't load public key" — the
  sandbox denying `~/.ssh`, not a missing key; retry with it disabled.

## File Structure

| File | Responsibility |
|---|---|
| `tools/dev/render-screenshot.sh` (create) | Transcript → static SVG, shared dark theme, licence header |
| `assets/quickstart/families/<family>/<name>.txt` (create ×~22) | The authored terminal text |
| `assets/quickstart/families/<family>/<name>.svg` (create ×~22) | Generated; never hand-edited |
| `assets/quickstart/families/<family>-first-run.svg` (delete ×9) | Retired — showed setup's arc, not the family's |
| `assets/quickstart/magpie-setup.svg` (re-cut) | Begins after the prerequisite: the `/magpie-setup` run only |
| `docs/*/README.md` × 10 (modify) | The callout, then the screenshots, replacing the first-run recording |
| `tools/dev/check-quickstart-recording.py` (modify) | Pairing, regeneration-staleness, per-family coverage; keeps parse / header / size / embedded / orphan |
| `tools/dev/tests/` (create) | Tests for the reworked checker |
| `assets/quickstart/README.md` (modify) | The recipe, and why authored beats captured |

---

### Task 1: The renderer

Build and prove the generator before authoring twenty-two transcripts against
it.

**Files:**
- Create: `tools/dev/render-screenshot.sh`
- Create: `assets/quickstart/families/pairing/self-review.txt` (the pilot)
- Create: `assets/quickstart/families/pairing/self-review.svg` (generated)

**Interfaces:**
- Produces: the CLI contract every later task uses —
  `tools/dev/render-screenshot.sh <path.txt>` writes `<path.svg>` beside it;
  `--all` renders every `.txt` under `assets/quickstart/families/`;
  `--check` renders to a temp file and diffs, exiting non-zero on drift.
- Produces: the SVG's shape — the theme, the licence header position, and the
  absence of any non-deterministic field — which Task 4's checker asserts.

- [ ] **Step 1: Write the pilot transcript**

`assets/quickstart/families/pairing/self-review.txt` — the literal terminal
text for a typical `magpie-pairing:self-review` run. Keep it under ~20 lines.
No version strings, no counts a minor change would move.

```text
> /magpie-pairing:self-review

  Reviewing 4 changed files against origin/main

  BLOCKING
    src/cache.py:88   unchecked dict access on a caller-supplied key

  NON-BLOCKING
    src/cache.py:12   module docstring omits the eviction policy
    tests/test_cache.py:40   asserts the mock, not the behaviour

  Nothing was sent, posted, or merged — the report is the output.
```

- [ ] **Step 2: Write the renderer**

`tools/dev/render-screenshot.sh`, executable, with the ASF licence header the
other scripts in `tools/dev/` carry. It must:

- take a `.txt` path and write the sibling `.svg`;
- emit a fixed-width text block in the shared dark theme (background,
  foreground and accent taken from `record-svg.sh` so the two sets look like
  one);
- size the viewBox from the transcript's longest line and line count;
- XML-escape `&`, `<`, `>` in the content;
- prepend the Apache licence header as an XML comment;
- write **nothing** that varies between runs — no date, no uuid, no hostname;
- support `--all` and `--check` as described in Interfaces;
- fail with a clear message when the `.txt` is missing or empty.

Document it in `tools/dev/README.md` in the same table row style as its
neighbours — `check-doc-sync` enforces that every script there is named.

- [ ] **Step 3: Prove determinism**

```bash
tools/dev/render-screenshot.sh assets/quickstart/families/pairing/self-review.txt
cp assets/quickstart/families/pairing/self-review.svg /tmp/first.svg
tools/dev/render-screenshot.sh assets/quickstart/families/pairing/self-review.txt
diff /tmp/first.svg assets/quickstart/families/pairing/self-review.svg && echo DETERMINISTIC
```

Expected: `DETERMINISTIC`. If it differs, find the varying field and remove it
— a renderer that is not byte-stable makes Task 4's staleness check impossible
and this task is not done.

- [ ] **Step 4: Look at it once**

Open the SVG. Check it is legible, that nothing is clipped at the right edge,
and that it reads as a terminal. One pass of fixes for what you see; do not
build a review loop.

- [ ] **Step 5: Commit**

```bash
git add tools/dev/render-screenshot.sh tools/dev/README.md assets/quickstart/families/pairing/
git commit -m "feat(dev): render authored terminal transcripts to static SVG

The family recordings were captures, which meant a capture session
whenever output moved and nine files that all showed the same arc.

This renders a committed .txt to a static .svg on the recorder's theme,
deterministically -- same input, same bytes -- so a checker can prove an
SVG still matches its source. No Node: the recorder needs svg-term-cli,
this does not, so it runs in CI and on a fresh clone.

Generated-by: Claude Opus 5"
```

---

### Task 2: Twenty-two transcripts

**Files:**
- Create: `assets/quickstart/families/<family>/<name>.{txt,svg}` for the ten
  families, two or three each

**Interfaces:**
- Consumes: Task 1's CLI and theme.
- Produces: the file tree Task 3 embeds and Task 4 checks.

- [ ] **Step 1: Choose what each family shows**

Two or three per family. Pick the commands from that family's *Try these
first* section — they are already the things a newcomer is told to run. Prefer
the skill whose output is most characteristic of the family over the one that
is merely first alphabetically.

Write the list down before authoring any of them, and check it against the
family's skill list so a family's headline skill is not the one you left out.

- [ ] **Step 2: Author them**

One `.txt` per screenshot, each under ~20 lines, following the pilot's shape.
The Global Constraints on secrecy and cosmetic robustness apply to every one.
For `security`, invent tracker numbers and use a scratch tracker name — a real
take would put an embargoed report in a public repository permanently.

- [ ] **Step 3: Render them all**

```bash
tools/dev/render-screenshot.sh --all
tools/dev/render-screenshot.sh --check
```

Expected: the first writes ~22 SVGs, the second exits 0.

- [ ] **Step 4: Commit**

```bash
git add assets/quickstart/families/
git commit -m "docs: author screenshots for the ten skill families

Two or three per family, drawn from the commands each family's README
already tells a newcomer to run first.

Authored rather than captured: a screenshot's job here is to show the
shape of a run, and authoring is what makes twenty-two of them
maintainable. The .txt is the source and reviews as a diff; the .svg is
generated from it and never hand-edited.

Generated-by: Claude Opus 5"
```

---

### Task 3: Callouts, and the recordings retired

**Files:**
- Modify: `docs/*/README.md` × 10
- Delete: `assets/quickstart/families/<family>-first-run.svg` × 9

**Interfaces:**
- Consumes: Task 2's SVG paths.
- Produces: the embed pattern Task 4's "embedded by the docs" check asserts.

- [ ] **Step 1: Establish the shape on one file**

In `docs/pairing/README.md`, between the intro prose and the *Install* section:

```markdown
> [!TIP]
> **Why this family**
> - Review your own diff before a maintainer spends their time on it
> - Findings split into blocking and non-blocking, so the nits do not drown
>   the real problems
> - Nothing is sent, posted, or merged — the report is the output

![A `/magpie-pairing:self-review` run: four changed files reviewed against
origin/main, one blocking finding and two non-blocking](../../assets/quickstart/families/pairing/self-review.svg)
```

Three bullets, each a benefit rather than a feature. Alt text describes what
the screenshot shows, not that it is a screenshot.

- [ ] **Step 2: Remove the first-run section**

Delete the *The first run* subsection and its `![…](…-first-run.svg)` embed.
The pre-flight behaviour it described is real and still documented — in the
quick start, which is where it belongs, because it is setup's arc rather than
the family's. Do not delete the sentence explaining that the check is silent
once set up if the README makes it in its own voice; delete the recording and
the section built around it.

- [ ] **Step 3: Apply to the other nine**

Same shape. `setup`'s README has no first-run recording to remove — it embeds
`magpie-setup.svg`, which stays. Give it a callout and screenshots like the
rest.

- [ ] **Step 4: Delete the nine recordings**

```bash
git rm assets/quickstart/families/*-first-run.svg
grep -rn "first-run.svg" docs/ assets/ tools/ || echo "no references remain"
```

Expected: nine deletions, then `no references remain`.

- [ ] **Step 5: Verify**

```bash
prek run --all-files doctoc
prek run --all-files markdownlint-cli2
prek run --all-files lychee
```

Expected: all pass. lychee proves every embed path resolves.

- [ ] **Step 6: Commit**

```bash
git add -A docs/ assets/
git commit -m "docs: give each family a benefit callout and its own screenshots

Every family README opened with a recording of the same thing: a
pre-flight failing on an unadopted repo. That is setup's arc, and nine
copies of it under ten families taught a reader nothing about what the
families do.

Each README now leads with what the family buys you, then shows that
family actually running. The nine first-run recordings are deleted.

Generated-by: Claude Opus 5"
```

---

### Task 4: Rework the checker

**Files:**
- Modify: `tools/dev/check-quickstart-recording.py`
- Create: `tools/dev/tests/test_check_quickstart_recording.py`
- Modify: `assets/quickstart/README.md`

**Interfaces:**
- Consumes: Task 1's determinism guarantee and Task 2's tree.
- Produces: nothing downstream — this is the closing task.

- [ ] **Step 1: Write the failing tests**

Following the fixture style in `tools/dev/tests/test_check_doc_sync.py` (a
`repo` fixture that `chdir`s into a tmp tree, an `_errors` helper). Cover:

- a `.txt` with no `.svg` beside it → reported;
- an `.svg` with no `.txt` → reported as an orphan;
- an `.svg` that does not match what the renderer produces from its `.txt` →
  reported as stale;
- a family directory with no screenshots at all → reported;
- a surviving `*-first-run.svg` → reported as retired;
- a clean tree → silent.

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run --project tools/dev --group dev pytest tools/dev/tests/test_check_quickstart_recording.py -q
```

Expected: failures naming the functions that do not exist yet.

- [ ] **Step 3: Rework the checker**

Keep the existing parse, licence-header, size-cap, embedded-by-the-docs and
orphan checks — they apply to `magpie-setup.svg` as much as to the new set.

Add: transcript/SVG pairing; the regeneration-staleness check (shell out to
`render-screenshot.sh --check`, or re-render to a temp file and compare); and
per-family coverage, so a family with no screenshots fails. Add the retirement
guard: any `*-first-run.svg` under `assets/quickstart/families/` fails, as does
any doc referencing one.

Drop the placeholder machinery if no placeholders remain, and say so in the
commit rather than leaving dead code that reads as still-used.

- [ ] **Step 4: Run everything**

```bash
uv run --project tools/dev --group dev pytest tools/dev/tests/ -q
python3 tools/dev/check-quickstart-recording.py
uv run --project tools/dev --group dev ruff check tools/dev/
uv run --project tools/dev --group dev ruff format --check tools/dev/
uv run --project tools/dev --group dev mypy tools/dev/check-quickstart-recording.py
```

Expected: all pass.

- [ ] **Step 5: Update the assets README and commit**

Rewrite `assets/quickstart/README.md`: one recording plus an authored set,
how to add a screenshot, why authored rather than captured, and the one thing
the checker cannot prove — that a transcript still matches what the skill
prints.

```bash
git add tools/dev/ assets/quickstart/README.md
git commit -m "feat(dev): check the authored screenshots regenerate

An authored SVG can drift from its source silently, which is the one
weakness a captured file does not have.

The checker gains transcript/SVG pairing, a regeneration-staleness check
that re-renders and compares, and per-family coverage, plus a guard that
the retired first-run recordings stay retired. The parse, licence-header,
size-cap and embed checks are unchanged.

What it still cannot prove: that a transcript matches what the skill
prints today. That is the accepted cost of not re-capturing, and the
assets README says so.

Generated-by: Claude Opus 5"
```

---

### Task 5: Re-cut the setup recording

Separate from the rest because it needs a terminal, a scratch project, and a
human — it cannot be done by an agent in CI.

**Files:**
- Modify: `assets/quickstart/magpie-setup.svg`

- [ ] **Step 1: Check whether it is still a placeholder**

```bash
grep -c "data-magpie-placeholder" assets/quickstart/magpie-setup.svg
```

If it is a placeholder, nothing real is lost and the re-cut is simply the
first capture. If it is a real recording, it opens with the marketplace
install, which Subsystem B made a prerequisite — so it must be re-cut to begin
at `/magpie-setup`.

- [ ] **Step 2: Record it**

Per `assets/quickstart/README.md`: in a scratch project, from a real terminal,
not in a Magpie checkout. Begin **after** the marketplace install — the run
starts at `/magpie-setup`.

```bash
tools/dev/record-svg.sh setup
```

- [ ] **Step 3: Verify and commit**

```bash
python3 tools/dev/check-quickstart-recording.py
```

```bash
git add assets/quickstart/magpie-setup.svg
git commit -m "docs: re-cut the setup recording to start after the prerequisite

The marketplace install is a one-time prerequisite with its own page, so
the recording no longer opens with it. It starts where the reader is:
at /magpie-setup.

Generated-by: Claude Opus 5"
```

---

## Self-review

**Spec coverage.** The design's C section names four things: the benefit
callout (Task 3), the authored screenshots and their renderer (Tasks 1–2), the
retirement of the nine recordings and the re-cut of `magpie-setup.svg`
(Tasks 3 and 5), and the reworked checker (Task 4). All four are covered.

**Sequencing.** Task 1 proves determinism before Task 2 authors twenty-two
files against it, because a renderer that is not byte-stable makes Task 4
impossible and would waste all of Task 2. Task 5 is last and separable — it
needs a human at a terminal, so it must not block the rest.

**Type consistency.** The renderer's contract (`<path.txt>`, `--all`,
`--check`) is stated once in Task 1's Interfaces and used unchanged in Tasks 2
and 4.

**Known gap, carried from the design.** Nothing can prove a transcript still
matches what a skill prints. The checker proves the `.svg` matches the `.txt`;
the `.txt`'s fidelity is a human's judgement. Task 4 requires the assets README
to say so plainly rather than let a reader assume the check is stronger than it
is.

**Open question for the implementer, not a defect.** Task 2 says two or three
screenshots per family without fixing the number. That is deliberate — a
two-skill family and a fifteen-skill family do not warrant the same coverage —
but it means the total (~22) is an estimate, and Task 4's per-family check must
assert *at least one*, not an exact count.
