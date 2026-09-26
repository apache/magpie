---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: optimize-skill
family: utilities
mode: Meta
description: >-
  Make an existing framework skill leaner without changing its behavior.
  Diagnose context-cost smells, propose the applicable optimization passes,
  and validate before and after every approved change.
when_to_use: >-
  When the user asks to optimize, shorten, split, de-hardcode, rewrite, or
  reduce the context cost of an existing skill, or an audit flags more than
  500 lines or hardcoded values. For a new skill, use write-skill.
capability: capability:authoring
surface_hash: sha256:be9968c266788028
license: Apache-2.0
measured_tokens: 3036
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory
     <tracker>        → value of `tracker_repo:` in <project-config>/project.md
     <upstream>       → value of `upstream_repo:` in <project-config>/project.md
     <framework>      → `.apache-magpie/apache-magpie` in adopters; `.` in
                        the framework standalone -->

# optimize-skill

<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently.
One command answers it and carries its own rules; there is nothing else to
read.

Run the checker with this skill's own frontmatter `name:` and
`surface_hash:`, and one `--requires` for each `requires_config:` entry:

```bash
PYTHONPATH=.apache-magpie-local python3 -m setup_preflight \
  --skill <name> --hash <surface_hash> [--requires <file>]...
```

- **`{"verdict": "ok"}`** → **silent**. Continue into the work the user
  asked for and say nothing about pre-flight. This is the ordinary answer.
- **`{"verdict": "action", ...}`** → each finding names a section, and
  `rules` carries that section's text. Follow it. The `facts` are the
  inputs; what to propose, and what may not be done, are in the rules
  rather than here. **Act on a finding only through its rules.**
- **The command did not run at all** — no such module, a non-zero exit, no
  `python3` — → never read that as a pass, and do not re-derive the check
  by hand: it lives in code so that there is one version of it. If the
  project has **no** `.apache-magpie.lock`, `.apache-magpie-local/` or
  `.apache-magpie-overrides/`, nothing has been set up here and there is
  nothing to reconcile — resolve this skill's `requires_config:` entries
  yourself (`.apache-magpie-local/<file>` first, then
  `.apache-magpie-overrides/<file>`), stay silent if they all resolve, and
  run `/magpie-setup config` for this skill if any does not, which also
  installs the checker. Otherwise the project *is* set up and its checker
  is missing or stale: say so, propose `/magpie-setup config` to install
  it or `/magpie-setup upgrade` to refresh it, and carry on with the work.

**Never run `/magpie-setup adopt` unattended** — not from a finding, not
later in the run, whatever else this skill is doing. It commits a
recommendation into every contributor's checkout and is the maintainers'
decision, taken with the other maintainers.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic.

<!-- END MAGPIE PREFLIGHT -->

Make an existing skill leaner without changing its behavior.

The first six passes preserve instruction wording while moving,
rewiring, or extracting content: five live in
[`patterns.md`](patterns.md), with extract-code below.
The seventh, [`rewrite.md`](rewrite.md), changes wording with the
maintainer writing each paragraph and teaching the skill their style.

The validator must be green before and after an approved pass.
For a new skill, use [`write-skill`](../write-skill/SKILL.md).

This skill reads only framework files, so the external-content rules do
not apply to it.

## What counts as small enough

Measure two budgets, set from the catalogue median when this skill was
written.
A skill over either target is an outlier.

| | target | why |
|---|---|---|
| `SKILL.md` body, pre-flight block excluded | **5,000 tokens** | paid on every invocation of that skill |
| `description` + `when_to_use` | **200 tokens** | paid in *every session*, for every skill at once, invoked or not |

Measure both before Step 1 and again at Step 4:

```bash
uv run --project tools/skill-token-count skill-token-count --write
```

Prioritize the always-on budget.
The body costs only when invoked; frontmatter costs in every session for
every skill.

Reference baseline: 75 skills; body median 4,614 tokens, p90 10,613,
largest 28,346; always-on median 200, largest 398.
`PRINCIPLES.md` P15's 500-line structural cap still applies.

Report both numbers in Step 5 whether or not the pass moved them.

## Inputs

- **Target** — a skill name, directory, or `SKILL.md` path.
- **`--all`** or **`over:<N>`** — diagnose and rank every skill without
  editing; the default threshold is the 500-line P15 cap.
- **`pass:<name>`** — restrict diagnosis to named passes; otherwise
  propose every applicable pass.

With no target or selector, diagnose everything read-only and let the
maintainer choose.

## Prerequisites

`uv` runs the validator; stop if it is unavailable.
Use `git` to isolate the diff, preferably on a clean tree or branch.
Use `doctoc` when headings move, or report the manual step if it is
unavailable.

## Step 0 — Check the ground

Resolve the target to a real skill directory and require a **green**
validator before editing.
Hand back baseline failures for correction; optimization starts from a
working skill.
Keep the diff isolated and reviewable.

## Step 1 — Diagnose

Run every diagnostic in [`patterns.md`](patterns.md) and report one row
per smell: the pass that addresses it, the evidence (`path:line`, line
count, the construct), and how big a change it implies. Read-only.

The smells, in the order their passes apply:

1. **Oversized body** — past the 500-line cap, or one section
   dominating. → *split*
2. **Concrete names** — adopter-specific values baked in instead of
   resolved from `<project-config>`. → *config-lift*
3. **Bulk reads** — pulling a whole issue or artefact into context to
   touch one field. → *out-of-context*
4. **Per-item round-trips** — N sequential fetches that could be one
   batch. → *fetch-upfront*
5. **No cheap pre-filter** — spending a model pass on items a
   deterministic check would skip. → *preflight-classifier*
6. **Embedded code** — shell or Python living inside the body, paid for
   on every invocation although a model never needs to read it. →
   *extract-code*
7. **Verbose prose** — the structure is right and the body still reads
   twice as long as it needs to. → *rewrite*, see
   [`rewrite.md`](rewrite.md)

For a sweep, rank by cap overflow times distinct smells and stop there.

## Step 2 — Propose

Propose applicable passes from lowest to highest blast radius: file
move, content lift, tool rewire, then rewrite because only it changes
wording.
For each pass, name the files, expected delta, and guarantee from
[`patterns.md`](patterns.md).

Propose only. The maintainer picks which passes run, and in what order.

## Step 3 — Apply one pass at a time

**Restructure passes** (*split*, *config-lift*) move exact text.
Use `git mv` for a whole file; otherwise move identical bytes and leave
a one-line pointer.

**Rewire passes** (*out-of-context*, *fetch-upfront*,
*preflight-classifier*) change execution, not decisions.
Route through a deterministic tool such as
[`github-body-field`](../../../../tools/github-body-field/README.md) or
[`github-rollup`](../../../../tools/github-rollup/README.md).
If human-facing proposals change, stop and use normal review.

**The extract-code pass** removes complete programs from model context.
Keep the command's purpose and output interpretation in the body, then
choose the destination by operational need:

- **Sibling `scripts/`** — default for a dependency-free command.
- **A `tools/` project** — for dependencies, tests, or reuse outside the
  skill; follow `tools/AGENTS.md` for its README, declared capability and
  prerequisites, and workspace entry.
- **The vetted-ops catalogue** — for a read-only operation with closed
  parameters that would otherwise prompt every run.
  Adding one requires reviewed changes to `ops.py` and the caller's
  grant, so propose it and stop.

Check prompt cost before choosing; do not trade tokens for a human
approval on every invocation.
Extract code **byte-identically** because paraphrasing changes the
program.

Do not extract command *shapes* containing runtime placeholders such as
`<tracker>`, `<N>`, or `<target>`.
They are instructions written in shell, not runnable programs.

Catalogue evidence shows this pass is rare: only 482 of roughly 28,700
tokens in shell and Python fences were multi-line and placeholder-free,
mostly too small to beat a pointer line.
It applied to `setup-isolated-setup-doctor`, whose six deterministic
probes used 2,971 tokens, or 59% of its budget.
Require all three traits: **complete, large enough to matter, and
unnecessary for the model to read**.

**The rewrite pass** follows [`rewrite.md`](rewrite.md).
The maintainer writes each paragraph; apply their earlier edits to later
drafts.

**A moved heading takes every reference with it:**

- **Eval `step-config.json`** — update `skill_md` and `step_heading`.
  Find matches with `grep -rl '<heading text>'
  tools/skill-evals/evals/`.
- **Anchor links** — update `other.md#the-heading` references; whole-tree
  `lychee` verifies them.
- **Heading levels** — a moved mid-body block may need to become a valid
  top-level section.
  This is the only byte a split may change, and its anchor and eval
  matcher must follow.

Only the eval suite catches a stale `step-config.json` extraction.

After each pass, regenerate the TOC if headings moved and re-run the
validator. One pass per commit.

## Step 4 — Prove nothing broke

Require the Step 0 validator result, and both budgets must have moved the
right way.

**Run the skill's eval suite if it has one**, at
`tools/skill-evals/evals/<skill>/`:

```bash
tools/skill-evals/magpie-run-evals.sh tools/skill-evals/evals/<skill>
```

Run it before the first pass and compare; an after-only run cannot
distinguish regressions from baseline failures.

If an unchanged case flips, name it as nondeterministic and let the
maintainer decide rather than claiming either result proves safety.

A missing suite does not block the pass, but report that the validator
was its only gate.

For restructure, match body deletions to sibling additions plus the new
pointer.
For rewire, show that human-facing proposals stayed unchanged.
For rewrite, the approved paragraph diff is the record.

If the validator goes red, or you cannot show the behaviour held,
**revert the pass**. Never ship half of one.

## Step 5 — Hand back

Report files, delta, validator result, and evidence per pass.
Do not commit or open a PR unless asked.
After rewrite, propose learned style rules from
[`rewrite.md`](rewrite.md).

If it was a sweep, restate what is still on the list.

## Hard rules

- Preserve behavior; only maintainer-written rewrite wording may change.
- Move identical bytes except for a necessary heading-level change, and
  update every heading reference.
- Propose before applying; never batch passes.
- Require a green validator, never a relaxed one, and measure both budgets
  and evals before and after every pass.
- Propose learned style rules as a visible diff; never write them
  silently.
- Never touch the snapshot; framework changes go through an
  `apache/magpie` PR.

## References

- [`patterns.md`](patterns.md) — the behaviour-preserving passes.
- [`rewrite.md`](rewrite.md) — the paragraph-by-paragraph rewrite and
  the style-learning loop.
- [`write-skill`](../write-skill/SKILL.md) — authoring a new skill.
- [`tools/skill-and-tool-validator`](../../../../tools/skill-and-tool-validator/README.md)
  — the gate.

## Learned style rules

Written by the rewrite pass at the end of a session, as a proposed
diff. Bullets only — a heading here would move this skill's
`surface_hash` and tell every adopter their configuration went stale
over a wording preference.

<!-- BEGIN LEARNED STYLE -->
<!-- END LEARNED STYLE -->
