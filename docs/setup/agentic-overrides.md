<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Agentic overrides — modifying framework workflows in an adopter](#agentic-overrides--modifying-framework-workflows-in-an-adopter)
  - [Two directories, one lookup chain — for overrides *and* configuration](#two-directories-one-lookup-chain--for-overrides-and-configuration)
    - [`.gitignore`, and the case where there is none](#gitignore-and-the-case-where-there-is-none)
  - [What an override file may contain](#what-an-override-file-may-contain)
    - [Skip a step](#skip-a-step)
    - [Replace a step](#replace-a-step)
    - [Add a step](#add-a-step)
    - [Pre-empt a decision-table row](#pre-empt-a-decision-table-row)
  - [What an override file should explain](#what-an-override-file-should-explain)
    - [Where override files come from](#where-override-files-come-from)
  - [How a framework skill consults overrides](#how-a-framework-skill-consults-overrides)
  - [One-shot defaults run](#one-shot-defaults-run)
  - [Hard rules](#hard-rules)
  - [Reconciliation on framework upgrade](#reconciliation-on-framework-upgrade)
  - [Upstreaming an override](#upstreaming-an-override)
  - [Why agentic, not declarative?](#why-agentic-not-declarative)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Agentic overrides — modifying framework workflows in an adopter

The framework's skills are project-agnostic by design. An
adopter project that needs to modify a framework workflow's
behaviour — different defaults, an extra step, a skipped step,
a different tone — does **not** fork the framework, does **not**
modify the framework's snapshot in `.apache-magpie/`, and does
**not** copy a framework skill into their own
`.claude/skills/`. Instead, they write an **override file**:
agent-readable markdown that the framework skill consults at
run-time and applies before executing default behaviour.

This document is the **contract** between adopter authors of
override files and framework authors of skills that read them.

## Two directories, one lookup chain — for overrides *and* configuration

Framework skills consult **two** directories in precedence order,
**per file, first hit wins**. The same two directories, and the same
rule, carry both kinds of adopter-side content:

- **Configuration** — facts about the project a skill reads: the
  upstream repo, the tracker, the committers team, the release
  trains. Scaffolded from
  [`projects/_template/`](../../projects/_template/README.md), and
  what `<project-config>` resolves to.
- **Overrides** — deliberate changes to how a skill behaves,
  named after the skill they modify.

The two directories:

1. **`.apache-magpie-local/`** — personal, gitignored, never
   committed and never pushed. Written by
   [`/magpie-setup config`](../../skills/setup/config.md). This is
   where an individual configures Magpie for themselves, and it
   **works on a repo that has not adopted Magpie** — which is the
   point of it. Nothing here asks the project for permission, and
   nothing here is visible to anyone else.

2. **`.apache-magpie-overrides/`** — committed, project-wide.
   Written by [`/magpie-setup adopt`](../../skills/setup/adopt.md),
   either scaffolded directly or promoted from (1). Every contributor
   who clones the repo gets these.

```text
<adopter-repo>/
├── .apache-magpie-local/                (gitignored, per-person)
│   ├── project.md                       config — yours
│   ├── pr-management-config.md          config — yours
│   └── <framework-skill-name>.md        override — yours
├── .apache-magpie-overrides/            (committed, project-wide)
│   ├── README.md
│   ├── project.md                       config — the project's
│   └── <framework-skill-name>.md        override — the project's
```

**Local wins, per file.** A skill reading `project.md` takes the local
copy if there is one and the committed copy otherwise; it makes that
decision file by file, so you can hold one file locally and take every
other from the project. For an override, the local file's instructions
are applied first and the committed file's are also applied unless the
local one says to skip it. Neither directory is required to exist; a
skill that finds neither proceeds with framework defaults.

The consequence worth knowing: **once the project commits a file you
also hold locally, yours keeps winning.** `/magpie-setup verify`
reports every local file that shadows a committed one, and
`/magpie-setup adopt` offers to drop the redundant ones as it
promotes. That is the cost of the rule being the same for
configuration as for overrides, and it is reported rather than
silent.

### `.gitignore`, and the case where there is none

`/magpie-setup install` and `/magpie-setup adopt` add
`/.apache-magpie-local/` to the adopter repo's `.gitignore`.

`/magpie-setup config` does **not**: `.gitignore` is a committed
file, and a sub-action whose whole promise is that it writes nothing
anyone else will see must not start by editing one. It writes the
same exclusion to **`.git/info/exclude`** instead — per-clone, never
committed, needs nobody's permission. On a repo that has already
adopted, the `.gitignore` line is there and the exclude entry is
harmless duplication.

To do it by hand:

```text
/.apache-magpie-local/
```

## What an override file may contain

Free-form agent-readable markdown. The agent interprets it. No
templating engine, no patch tool, no DSL. The override author
writes what they want to change, and the framework skill applies
it on every invocation.

Common shapes:

### Skip a step

```markdown
### Override 1 — Skip the workflow-approval auto-approve

For first-time-contributor PRs, the default flow approves the
workflow run automatically after diff inspection. Skip that
step entirely; we approve workflow runs by hand on this repo.
```

### Replace a step

```markdown
### Override 2 — Replace the close-comment template

Replace the body the `close` action posts with the project-
specific wording in
[`<adopter-repo>/.github/CONTRIBUTING-pr-quality.md`](../.github/CONTRIBUTING-pr-quality.md)
section *"PRs we close as out of scope"*. Keep the AI-attribution
footer.
```

### Add a step

```markdown
### Override 3 — Always tag @core-maintainers on first comment

Before posting any comment on a PR for the first time, add a
`@apache/airflow-core-maintainers` mention so the team gets a
notification. Do not add it on subsequent comments on the same
PR.
```

### Pre-empt a decision-table row

```markdown
### Override 4 — Treat backport PRs as already-triaged

Any PR whose base branch matches `v[0-9]-[0-9]-test` is
auto-classified as `already-triaged` regardless of triage
markers. Skip the `mark-ready` action; backports go straight to
the `pr-management-code-review` queue when their CI passes.
```

## What an override file should explain

Every override file should answer two questions for a future
maintainer (or a future agent on a later run):

1. **Why does this adopter need to deviate from the
   framework's default?** Often the answer is a project-
   specific convention, an existing tool the framework
   doesn't know about, or a deliberate softer/harder stance
   on a default policy.
2. **Should this be upstreamed?** If the override is widely
   useful, it belongs in the framework. The override file
   says so explicitly, and the next person running the
   `/magpie-setup override <skill>` flow takes the cue and
   opens a PR against `apache/magpie`.

### Where override files come from

Two paths write them, and both end at a human accepting a
specific file:

- **`setup override <skill>`** — the user names a skill and
  authors the override, scaffolded or opened for editing.
- **`setup adopt` step 4c** — when a skill family joins the
  floor, adopt reads the project's own process documents
  (`CONTRIBUTING.md`, `GOVERNANCE.md` and whatever else the
  maintainer confirms) and proposes an override for each
  place they contradict a default of a newly-adopted
  family's skills. Each candidate is shown with the line it
  came from and accepted, edited or rejected one at a time.

Nothing about this document's contract changes for the
second path. A proposed override is still a file the
maintainer approved, it still explains why, and the
[hard rules](#hard-rules) still bind it — in particular, a
deviation that would weaken a confirmation gate or the
safety baseline is dropped rather than written, and a
candidate with no quoted evidence in a real document is not
proposed at all. An override store is a record of decisions
the project made, and inference is not a decision.

## How a framework skill consults overrides

Every framework skill that supports overrides starts each
invocation with this opening protocol:

0. **Check for `--no-overrides`.** If the invocation passed
   the `--no-overrides` flag, skip steps 1–4 entirely — both
   override surfaces — and run against framework defaults for
   this invocation; see
   [One-shot defaults run](#one-shot-defaults-run). The safety
   baseline still applies. Still do step 5, reporting that the
   run used `--no-overrides` and naming the override files that
   existed but were not consulted, so the audit trail records
   the bypass rather than looking like a run with no overrides
   on disk. Otherwise, continue with step 1.
1. Read `<adopter-repo>/.apache-magpie-local/<this-skill>.md`
   (personal, gitignored) if it exists.
2. Read `<adopter-repo>/.apache-magpie-overrides/<this-skill>.md`
   (committed, project-wide) if it exists.
3. Surface the titles and override headlines
   (`### Override N — ...`) from both files to the user
   before doing anything else.  Indicate which file each
   came from so the user can tell personal from shared
   overrides at a glance.
4. Apply both sets of overrides: personal-local first, then
   committed.  Each `### Override N — ...` section modifies
   the skill's default behaviour for this run.  The agent
   interprets the instructions and adjusts the rest of the
   skill's flow accordingly.
5. After the skill finishes, recap which overrides were
   applied (source file + override headline), and any the
   agent decided not to apply with the reasoning, so the user
   has an audit trail.

A skill that does **not** yet support overrides documents
that explicitly in its `SKILL.md`. The
[`setup override`](../../skills/setup/overrides.md)
sub-action surfaces this gap and suggests opening a
framework-side issue requesting the hook.

## One-shot defaults run

Pass `--no-overrides` to any framework skill that supports
overrides to run that single invocation against framework
defaults, ignoring any override files that exist on disk.
The override files are **not** modified or deleted — they
are simply not consulted for this run.

```text
/magpie-pr-management:triage --no-overrides
/magpie-security:issue-triage --no-overrides
```

When `--no-overrides` is present the skill's opening
protocol changes: **skip steps 1–3 entirely** — do not
read, surface, apply, or recap any override file. The skill
proceeds immediately with its framework defaults, as if
neither `.apache-magpie-overrides/<skill>.md` nor any
personal override existed.

The **safety baseline** (confidentiality, privacy, and
security rules baked into the framework) still applies in
full — `--no-overrides` is not a safety bypass.  It only
removes the adopter-customisation layer.

Typical use cases:

- **Debugging**: reproduce the framework's default
  behaviour to determine whether an override is causing
  an unexpected result.
- **One-off clean run**: a release manager wants a
  pristine triage run without their personal overrides
  for this single check-in.
- **Override authoring**: run with defaults first to see
  what the framework produces, then compare against a
  run that applies the override under construction.

## Hard rules

These are baked into agent instructions across the framework.
A framework agent NEVER:

- Modifies the snapshot under
  `<adopter-repo>/.apache-magpie/`. The snapshot is a build
  artefact — every modification gets blown away on the next
  `/magpie-setup upgrade`. Local mods go into
  `.apache-magpie-local/` (personal) or
  `.apache-magpie-overrides/` (shared).
- Commits or pushes `.apache-magpie-local/` content. The
  personal override directory is gitignored by design — it
  carries per-person paths, credentials, and capability
  enablements the contributor has not chosen to share.
- Proposes overrides be merged in by editing the framework
  source in the snapshot. Framework changes go via PR to
  `apache/magpie`.
- Auto-rewrites override files on framework upgrades. When
  a framework upgrade restructures a skill that has an
  override, the agent surfaces the conflict and lets the
  human decide (the override expresses adopter intent —
  re-anchoring it correctly is human judgement, not
  pattern-matching).
- Weakens the safety, confidentiality, or privacy baseline
  from either override surface.  An override that attempts
  to do so is ignored and the conflict is surfaced.

## Reconciliation on framework upgrade

When `/magpie-setup upgrade` refreshes the snapshot, it
walks every override file and surfaces:

- Overrides whose target framework skill no longer exists
  (renamed or removed).
- Overrides that reference framework structure (step
  numbers, golden rules, decision-table rows) that has
  changed in the new framework version.

Both are surfaced as ⚠ — non-blocking, but the user re-
anchors the override against the new framework structure
before relying on it again. Until re-anchored, the framework
skill applies what it can interpret from the override and
reports anything it skipped.

**The always-on per-skill stamp check and `/magpie-setup reconcile`
apply to every adopted or configured project, snapshot pin and
marketplace floor alike — only the override-walk's *trigger*
differs.** Every skill's own pre-flight compares its shipped
`surface_hash` against the entry recorded for it in the
`reconciled:` stamp (see
[`locks.md`](../../plugins/magpie-setup/skills/setup/locks.md#the-reconciled-block--what-was-checked-not-what-to-install)),
regardless of install method, and a mismatch on either input it
covers — a `requires_config` change or a moved anchor — surfaces the
matching ⚠ inline, on that skill's own run, at no extra cost. A
project with no stamp yet, or whose overrides and configuration need
a full pass, gets it from `/magpie-setup reconcile`, the on-demand
sweep available to any adopted or configured project regardless of
method. Snapshot adopters (`git-branch`, `git-tag`, `svn-zip`)
additionally reach the walk above through `/magpie-setup upgrade`,
which refreshes the snapshot and then performs it — a second,
method-specific route to the same checks, not a different mechanism.
Marketplace adopters have no snapshot to refresh, so the always-on
stamp check and `reconcile` are the whole story for them; for
snapshot adopters the two run alongside `upgrade`, catching drift
between refreshes that nobody has run `upgrade` to surface yet.

## Upstreaming an override

If an adopter project's override is widely useful (e.g. a
behaviour the framework should ship by default for all
adopters), the right move is **a PR against the framework**:

1. Read the latest `apache/magpie` `main`.
2. Implement the change in the framework skill's source.
3. Open the PR.
4. Once merged, the next `/magpie-setup upgrade` in the
   adopter pulls the framework change.
5. The adopter's now-redundant override gets deleted.

The
[`setup override`](../../skills/setup/overrides.md)
sub-action prompts the user about upstreaming on every
override scaffold; the
[`security-issue-fix`](../../skills/security-issue-fix/SKILL.md)
and
[`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md)
skills know how to open a public PR — point them at the
framework repo.

## Why agentic, not declarative?

The first cut of an override mechanism would be templated:
a YAML schema, declared anchors per skill step, a runtime
patch. We deliberately rejected that:

- **Schemas drift.** Every framework restructure breaks
  every adopter's overrides. The framework's authors have
  to maintain backward-compatible anchor tags forever, or
  every upgrade is a synchronised override-rewrite event
  across every adopter.
- **Schemas force pre-thought.** The framework would have
  to anticipate every override an adopter might want and
  surface anchors for it. The agentic mechanism inverts
  this: adopters describe what they want, the agent figures
  out how to apply it against whatever shape the framework
  currently has. The framework is free to restructure;
  overrides are free to express intent in whatever
  granularity the user finds natural.
- **Agents already interpret natural-language workflow
  changes**. The whole framework is agent-readable
  markdown — having overrides be the same lets the agent
  apply them with the same comprehension primitives as
  the underlying skills.

Trade-off: agentic interpretation has variance. An override
that says "always tag @core-maintainers" might be applied
slightly differently across runs. The mechanism mitigates
this by:

1. Surfacing override application *before* skill execution
   so the user can correct ambiguity.
2. Recapping override application *after* skill execution
   for audit.
3. Keeping override files small and specific (the
   `/magpie-setup override` flow encourages one focused
   override per file, not a sprawling rewrite).

## Cross-references

- [`setup` skill](../../skills/setup/SKILL.md) — the entry point
  that manages the snapshot, scaffolds overrides, and adds the
  `.gitignore` entries for both override directories. Lists
  `--no-overrides` in its Inputs table as a recognised
  framework-level flag.
- [`overrides.md` sub-action](../../skills/setup/overrides.md) —
  interactive override creation (lets the user choose between the
  personal-local and committed surfaces).
- [Top-level README](../../README.md) — install flow.
- [`setup-status` skill](../../skills/setup-status/SKILL.md) —
  the adoption dashboard, which reports whether both override
  directories are present.
