<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Agentic overrides — modifying framework workflows in an adopter](#agentic-overrides--modifying-framework-workflows-in-an-adopter)
  - [Where override files live](#where-override-files-live)
  - [What an override file may contain](#what-an-override-file-may-contain)
    - [Skip a step](#skip-a-step)
    - [Replace a step](#replace-a-step)
    - [Add a step](#add-a-step)
    - [Pre-empt a decision-table row](#pre-empt-a-decision-table-row)
  - [What an override file should explain](#what-an-override-file-should-explain)
  - [How a framework skill consults overrides](#how-a-framework-skill-consults-overrides)
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

## Where override files live

```text
<adopter-repo>/.apache-magpie-overrides/
├── README.md                            (the dir's own readme,
│                                          scaffolded by
│                                          /magpie-setup adopt)
├── <framework-skill-name>.md            (e.g. pr-management-triage.md)
└── <other-framework-skill-name>.md
```

The directory is **committed** in the adopter repo (the whole
point is for overrides to ship with the project's repo).

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

## How a framework skill consults overrides

Every framework skill that supports overrides starts each
invocation with this opening protocol:

1. Read `<adopter-repo>/.apache-magpie-overrides/<this-skill>.md`
   if it exists. Surface the file's title and the list of
   override headlines (`### Override N — ...`) to the user
   before doing anything else.
2. Apply the overrides: each `### Override N — ...` section
   modifies the skill's default behaviour for this run. The
   agent interprets the instructions in the override section
   and adjusts the rest of the skill's flow accordingly.
3. After the skill finishes, recap which overrides were
   applied (and any the agent decided not to apply with the
   reasoning), so the user has an audit trail.

A skill that does **not** yet support overrides documents
that explicitly in its `SKILL.md`. The
[`setup override`](../../skills/setup/overrides.md)
sub-action surfaces this gap and suggests opening a
framework-side issue requesting the hook.

## Hard rules

These are baked into agent instructions across the framework.
A framework agent NEVER:

- Modifies the snapshot under
  `<adopter-repo>/.apache-magpie/`. The snapshot is a build
  artefact — every modification gets blown away on the next
  `/magpie-setup upgrade`. Local mods go into
  `.apache-magpie-overrides/`.
- Proposes overrides be merged in by editing the framework
  source in the snapshot. Framework changes go via PR to
  `apache/magpie`.
- Auto-rewrites override files on framework upgrades. When
  a framework upgrade restructures a skill that has an
  override, the agent surfaces the conflict and lets the
  human decide (the override expresses adopter intent —
  re-anchoring it correctly is human judgement, not
  pattern-matching).

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

- [`setup` skill](../../skills/setup/SKILL.md) — the entry point that manages the snapshot + scaffolds overrides.
- [`overrides.md` sub-action](../../skills/setup/overrides.md) — interactive override creation.
- [Top-level README](../../README.md) — adoption flow.
