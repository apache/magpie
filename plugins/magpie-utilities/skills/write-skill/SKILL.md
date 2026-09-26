---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: write-skill
family: utilities
mode: Meta
description: >-
  Write a new skill for the Apache Magpie framework, or bring an
  existing one up to current conventions. Scaffolds the directory,
  walks the house style and the prompt-injection defences, and
  validates before it ships.
when_to_use: >-
  When the user says "write a skill", "create a new skill", "add a
  skill for X", or wants an existing skill updated to the framework's
  current conventions. For making a skill leaner without changing what
  it does, use optimize-skill.
capability: capability:authoring
surface_hash: sha256:31626428a2545bce
license: Apache-2.0
measured_tokens: 2456
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory
     <tracker>        → value of `tracker_repo:` in <project-config>/project.md
     <upstream>       → value of `upstream_repo:` in <project-config>/project.md
     <framework>      → `.apache-magpie/apache-magpie` in adopters; `.` in
                        the framework standalone -->

# write-skill

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

Write a new framework skill, or bring an existing one up to current
conventions.

Three files carry the detail, each read when a step calls for it:
[`anatomy.md`](anatomy.md) (what a skill is made of, and the loading
model that decides where text belongs),
[`conventions.md`](conventions.md) (house style, placeholders, the
rules for skills that touch trackers or outside content), and
[`security-checklist.md`](security-checklist.md) (the nine
prompt-injection patterns in full). [`provenance.md`](provenance.md)
records where this skill came from.

To make an existing skill leaner without changing what it does, use
[`optimize-skill`](../optimize-skill/SKILL.md) instead. Step 7 runs it
against every new skill regardless.

## Step 1 — Get three concrete examples

Before writing anything, ask what the user will actually say, what the
agent does in response, and what the apply step is. Get three to five
real invocations, not paraphrases.

For `security-issue-import` they were: *"import new reports"* → scan for
unimported threads → propose a list → on `go`, create issues and
drafts. *"check for unimported security@ messages"* → the same.
*"import #<threadId>"* → one named thread.

If an example stays fuzzy, ask until it is concrete. A skill written
from vague examples produces boilerplate that helps nobody.

## Step 2 — Decide what goes where

For each example, sort the work into three buckets.

**Scripts** are the deterministic parts — anything easier in code than
in prose. **Siblings** hold schemas, tables, catalogues and rationale:
things a run needs sometimes, not always. **Assets** are templates the
skill writes out verbatim.

Most skills need a small `scripts/` and nothing else. Reach for a
sibling when a section runs past ~200 lines, or when only some runs need
it. [`anatomy.md`](anatomy.md) has the reasoning.

## Step 3 — Scaffold it

```bash
python3 <framework>/skills/write-skill/scripts/init_skill.py \
  <skill-name> --path skills/<skill-name>
```

This creates the directory, a `SKILL.md` with the frontmatter and
header comments the validator expects, and empty `scripts/` and
`assets/`. Skip this step for an existing skill.

## Step 4 — Write the body

Write the steps, the hard rules, and the references.
[`conventions.md`](conventions.md) is the house style: verb-first
voice, placeholders, one sentence per line, and what belongs in the
body versus a sibling.

Two things decide most of the shape. Every state-changing step is a
proposal the user confirms. Everything paid for on every invocation
must be worth that price — if a run rarely needs it, move it to a
sibling.

## Step 5 — Secure it, if it reads outside content

A skill reading Gmail, public PRs, mailing lists or findings files takes
the patterns in [`security-checklist.md`](security-checklist.md);
[`conventions.md`](conventions.md) summarises them. A skill reading only
framework files skips this step and says so in its body, so the next
reader knows the omission was deliberate.

## Step 6 — Validate

```bash
uv run --directory tools/skill-and-tool-validator --group dev \
  skill-and-tool-validate
```

It checks the frontmatter shape, placeholder discipline, the SPDX
header and internal links. Fix what it reports and run it again. CI
runs the same check, so a red skill does not merge.

## Step 7 — Optimize before you ship

A skill is written to be understood, and first drafts explain too much.
Run [`optimize-skill`](../optimize-skill/SKILL.md) against what you just
wrote — always, not only when it feels long. This is part of writing a
skill, not a later cleanup someone may or may not get to.

It checks the new skill against the two budgets in that skill's *What
counts as small enough*: the body under 5,000 tokens, and
`description` + `when_to_use` under 200. The second matters most. It is
paid in every session, for every skill at once, whether or not anyone
ever invokes this one — so a wordy description taxes people who will
never use the skill.

Take its restructuring passes; they move text without changing it. For
prose it offers the paragraph-by-paragraph rewrite, where you write the
words and it learns your style as it goes.

A new skill that cannot get under both budgets is usually doing two
jobs. Consider splitting it before accepting the size.

## Step 8 — Ship, then iterate

Use the skill on real work and watch where it goes wrong: a step whose
instructions were too loose, a missing reference, a script that would
have helped. Land each fix as its own change. The body is re-read on
every invocation, so a tightening here compounds.

When an adopter's `.apache-magpie-overrides/<skill-name>.md` has
accumulated something worth having upstream,
[`setup-override-upstream`](../../../magpie-setup/skills/override-upstream/SKILL.md)
walks the promotion.

## Hard rules

- **Every state-changing step is a proposal the user confirms.** No
  skill posts, edits or pushes on its own. This is the framework's
  load-bearing invariant.
- **Attacker-controlled text never enters a `gh` argument inside
  quotes.** Tempfile plus `-F field=@file`. Never `--body "$(cat …)"` —
  use `--body-file`. The exception is a regex-validated token such as
  `CVE-…`, where the validation is the gate.
- **`license: Apache-2.0` and a `capability:` in the frontmatter.** The
  validator enforces both. Pick capabilities from
  [`docs/labels-and-capabilities.md`](../../../../docs/labels-and-capabilities.md)
  and list all that apply rather than collapsing to one. If none fit,
  stop: either the taxonomy needs an entry or the skill is doing too
  much.
- **Credit adapted third-party content in
  [`NOTICE`](../../../../NOTICE).**
- **Never ship a skill that has not been through Step 7.** The budgets
  are the gate: body under 5,000 tokens, frontmatter under 200.

## References

- [`anatomy.md`](anatomy.md), [`conventions.md`](conventions.md),
  [`security-checklist.md`](security-checklist.md),
  [`provenance.md`](provenance.md) — this skill's detail files.
- [`scripts/init_skill.py`](scripts/init_skill.py) — Step 3's scaffold.
- [`optimize-skill`](../optimize-skill/SKILL.md) — making an existing
  skill leaner.
- [`AGENTS.md`](../../../../AGENTS.md) — framework authoring
  conventions and the external-content-as-data rule.
- [`tools/skill-and-tool-validator/`](../../../../tools/skill-and-tool-validator/)
  — Step 6's gate.
