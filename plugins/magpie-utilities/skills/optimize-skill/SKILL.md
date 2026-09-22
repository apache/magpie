---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-optimize-skill
family: utilities
mode: Meta
description: >-
  Make an existing framework skill leaner without changing what it
  does: split an oversized body into siblings, lift hardcoded values
  into placeholders, move bulk reads and per-item fetches out of
  context, and — with the maintainer writing the words — rewrite
  verbose prose paragraph by paragraph. Every pass is a proposal, and
  the validator is green before and after.
when_to_use: >-
  When the user says "optimize <skill>", "this SKILL.md is too long",
  "split <skill> into subdocs", "make <skill> read less into context",
  or "rewrite <skill> with me". Also after an audit flags an
  over-500-line body or hardcoded values. For a net-new skill, use
  write-skill.
capability: capability:authoring
surface_hash: sha256:be9968c266788028
license: Apache-2.0
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

Make an existing skill leaner without changing what it does.

There are two kinds of pass. The five in
[`patterns.md`](patterns.md) move and rewire text without altering a
word of the instructions. The sixth,
[`rewrite.md`](rewrite.md), changes the words — the maintainer writes
them, paragraph by paragraph, and the skill learns their style as it
goes.

The validator is the gate: green before the first pass, green after the
last. To write a skill from scratch, use
[`write-skill`](../write-skill/SKILL.md) instead.

This skill reads only framework files, so the external-content rules do
not apply to it.

## What counts as small enough

Two budgets, both measured rather than guessed. They were set at the
catalogue median when this skill was written, so half the skills already
met them; a skill past either one is an outlier, not merely large.

| | target | why |
|---|---|---|
| `SKILL.md` body, pre-flight block excluded | **5,000 tokens** | paid on every invocation of that skill |
| `description` + `when_to_use` | **200 tokens** | paid in *every session*, for every skill at once, invoked or not |

Measure both before Step 1 and again at Step 4:

```bash
uv run --project tools/skill-token-count skill-token-count --write
```

The always-on budget is the one to spend effort on first. A body only
costs when its skill runs; the frontmatter costs whether or not anyone
ever invokes it, multiplied by every skill in the catalogue. Cutting 200
tokens there beats cutting 2,000 from a body nobody triggers this week.

For reference when this was set: 75 skills, median body 4,614 tokens,
p90 10,613, largest 28,346; median always-on 200, largest 398.
`PRINCIPLES.md` P14's 500-line cap still applies as the structural
limit — these are the context budgets underneath it.

Report both numbers in Step 5 whether or not the pass moved them.

## Inputs

**Target** — a skill name, a directory, or a `SKILL.md` path.

**`--all`** or **`over:<N>`** — diagnose every skill instead, ranking
candidates without touching anything. The default threshold is 500
lines, the `PRINCIPLES.md` P14 cap.

**`pass:<name>`** — restrict to named passes. Default is to propose
every applicable one.

With no target and no selector, diagnose everything read-only and let
the maintainer choose.

## Prerequisites

`uv` runs the validator, which is the gate — without it, stop and say
so. `git` isolates the diff, so prefer a clean tree or a branch.
`doctoc` regenerates a TOC when headings move; if it is missing,
surface the manual step rather than skipping it quietly.

## Step 0 — Check the ground

The target must resolve to a real skill directory. The validator must
be **green before you start** — optimization is layered on a working
skill, not a way to fix a broken one, so hand back the failures and let
the maintainer fix correctness first. The working tree should be clean
enough that this diff is reviewable on its own.

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
6. **Verbose prose** — the structure is right and the body still reads
   twice as long as it needs to. → *rewrite*, see
   [`rewrite.md`](rewrite.md)

For a sweep, rank by cap overflow times distinct smells and stop there.

## Step 2 — Propose

Propose the applicable passes lowest-blast-radius first: a file move
before a content lift before a tool rewire, and the rewrite pass last
because it is the only one that changes wording. For each, state the
files touched, the expected delta, and the guarantee from
[`patterns.md`](patterns.md).

Propose only. The maintainer picks which passes run, and in what order.

## Step 3 — Apply one pass at a time

**Restructure passes** (*split*, *config-lift*) move text and change
none of it. Use `git mv` for a whole file; otherwise move the exact
bytes and leave a one-line pointer behind. Never paraphrase something
you moved — that is a behaviour change wearing a refactor's clothes.

**Rewire passes** (*out-of-context*, *fetch-upfront*,
*preflight-classifier*) change how a step runs, not what it decides.
They route through an existing deterministic tool such as
[`github-body-field`](../../../../tools/github-body-field/README.md) or
[`github-rollup`](../../../../tools/github-rollup/README.md). If a
rewire would change what the skill proposes to a human, it is not a
rewire — stop and take it through normal review.

**The rewrite pass** is different and has its own file:
[`rewrite.md`](rewrite.md). The maintainer writes the words; the skill
carries paragraphs one at a time and applies what it has learned from
their earlier edits to the ones that follow.

**A moved heading breaks things that point at it.** Before calling a
restructure pass done, follow every reference to the headings you moved:

- **Eval `step-config.json`** — a suite builds its prompt live from
  `skill_md` plus `step_heading`, so a heading that moved to a sibling
  leaves the suite extracting from a file that no longer contains it.
  Update both fields. `grep -rl '<heading text>'
  tools/skill-evals/evals/` finds them.
- **Anchor links** — `other.md#the-heading` anywhere in the tree.
  `lychee` catches these, which is why it runs over the whole tree
  rather than the diff.
- **Heading levels.** A block cut from mid-body starts at `###` and
  cannot open a new file, so it shifts a level. That changes the anchor
  *and* the `step_heading` string an eval matches on — so it is the one
  byte a split is allowed to change, and every reference has to follow.

Neither the validator nor `prek` sees the first of these. Only running
the suite does, which is the argument for Step 4 running it at all.

After each pass, regenerate the TOC if headings moved and re-run the
validator. One pass per commit.

## Step 4 — Prove nothing broke

The validator must return the same green it returned at Step 0, and the
budgets from *What counts as small enough* must have moved the right way.

**Run the skill's eval suite if it has one**, at
`tools/skill-evals/evals/<skill>/`:

```bash
tools/skill-evals/magpie-run-evals.sh tools/skill-evals/evals/<skill>
```

Run it **before the first pass as well**, and compare. A suite you only
ran afterwards cannot tell a regression from a case that was already
failing.

Some suites are not deterministic — the same unchanged tree grades
differently between runs. When a case flips, say so plainly instead of
treating either run as the verdict: name the case, say the suite varies,
and let the maintainer decide. Claiming a rewrite is proven safe on a
suite that cannot hold still is worse than admitting the gap.

A skill with no suite is not blocked, but say it has none — that is the
maintainer's cue that the validator is the only gate on this change.

For a restructure pass, show the moved bytes are the same bytes:
deletions in the body matching additions in the siblings, plus the new
pointer. For a rewire, show the proposals a human signs off on are
unchanged and only the cost moved. For a rewrite pass, the maintainer
approved each paragraph as it went, so the record is the diff itself.

If the validator goes red, or you cannot show the behaviour held,
**revert the pass**. Never ship half of one.

## Step 5 — Hand back

Per pass: files touched, the delta, validator result, evidence. Do not
commit or open a PR unless asked. After a rewrite pass, also propose
the learned style rules per [`rewrite.md`](rewrite.md).

If it was a sweep, restate what is still on the list.

## Hard rules

- **Structure changes, behaviour does not.** Except in the rewrite
  pass, where wording changes and the maintainer writes every word.
- **Moved bytes are identical bytes**, heading level excepted. A
  paraphrase during a move is a behaviour change in disguise.
- **A heading that moves takes its references with it** — eval
  `step-config.json`, anchor links, anything matching on the string.
- **Propose before applying**, every pass, never a batch.
- **The validator is the gate**, green before and after. A pass that
  needs it relaxed is not an optimization.
- **Learned style rules are a proposal too.** Show the diff; never
  write them silently.
- **Measure, before and after, every pass.** Both budgets and the eval
  suite. A pass reported without numbers is an opinion.
- **Never touch the snapshot.** Framework changes go via PR to
  `apache/magpie`.

## References

- [`patterns.md`](patterns.md) — the five behaviour-preserving passes.
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
