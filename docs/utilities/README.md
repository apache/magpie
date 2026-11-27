<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Skill tools](#skill-tools)
  - [Install & first runs](#install--first-runs)
  - [Skills](#skills)
  - [When to adopt this family](#when-to-adopt-this-family)
  - [Adopter contract](#adopter-contract)
  - [Status](#status)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<a id="utilities-skill-family"></a>
# Skill tools

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

Framework meta-skills — the tools you use to **discover, build, and maintain skills
themselves**, rather than to run a maintainership mode on your project. They
sit outside the MISSION mode taxonomy (Agentic Triage, Agentic Mentoring,
Agentic Drafting, Agentic Pairing, Agentic Autonomous): nothing here acts on
your issues, PRs, or contributor threads.
They are for skill authors and framework contributors.

---

> [!TIP]
> **Why this family**
> - See what is installed here and what the marketplace has that you have not taken
> - Author a new skill against the framework's conventions, including the eval suite that keeps it working
> - Report a framework bug from where you hit it, after checking nobody has already filed it

## Install & first runs

[Install & first runs](install.md) has the install command for this family,
the files to configure before the first run, and the skills to try first.

## Skills

| Skill | Purpose | Status |
|---|---|---|
| [`write-skill`](../../plugins/magpie-utilities/skills/write-skill/SKILL.md) | Author a new framework skill or update an existing one: frontmatter, placeholder convention, injection defenses, Privacy-LLM gate-check, and validator sign-off. | stable |
| [`optimize-skill`](../../plugins/magpie-utilities/skills/optimize-skill/SKILL.md) | Optimize an existing skill by applying restructuring patterns — split an oversized `SKILL.md` into linked sibling docs, trim frontmatter, and improve eval alignment. | stable |
| [`optimize-agents-md`](../../plugins/magpie-utilities/skills/optimize-agents-md/SKILL.md) | Make an agent-instruction file (`AGENTS.md`, `CLAUDE.md`) cheaper to load without losing a rule: measure its always-on cost, move task-only and subtree-only sections behind triggered pointers, and prove every normative sentence survived. | stable |
| [`list-skills`](../../plugins/magpie-utilities/skills/list-skills/SKILL.md) | Print a live index of every skill in this repository, grouped by family, with each skill's name and first-sentence description. | stable |
| [`skill-reconciler`](../../plugins/magpie-utilities/skills/skill-reconciler/SKILL.md) | Reconcile a skill's declared state (frontmatter, sibling docs, symlinks) against the framework's conventions and surface discrepancies with proposed fixes. | stable |

---

## When to adopt this family

Adopt `utilities` if you intend to **write or maintain your own skills** —
whether contributing them back to Magpie or keeping them in your own project.
If you are only adopting existing skills to run on your project, you do not
need this family; the [`setup`](../setup/README.md) family is your starting
point instead.

---

## Adopter contract

The utilities skills make no state changes to your project's tracker, label
set, or shared infrastructure. `list-skills` is read-only; `write-skill`,
`optimize-skill` and `optimize-agents-md` only create or edit files under your
control, which you review before committing.

`optimize-skill` and `optimize-agents-md` work on your project's own skills and
instruction files, not only Magpie's. Your eval suites for them live under
`.apache-magpie-overrides/evals/` (`optimize-agents-md` seeds one from its
template), and they run with the eval runner Magpie installs as
`<framework>/tools/skill-evals`: under the secure setup, through
`~/.claude/scripts/magpie-run-evals.sh`. A house style the rewrite pass learns
from your edits is kept in `.apache-magpie-overrides/optimize-skill.md`.

## Status

**Stable.** All four skills are shipped and validate under
`skill-and-tool-validate`. They are framework-authoring tools, so they evolve
with the framework's own conventions rather than with adopter pilots.

---

## Cross-references

- [`docs/modes.md` § Meta](../modes.md#meta) — why
  these skills sit outside the maintainership-mode taxonomy.
- [`docs/spec-driven-development.md`](../spec-driven-development.md) — the
  authoring loop `write-skill` and `optimize-skill` support.
