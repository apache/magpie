<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Utilities skill family](#utilities-skill-family)
  - [Install & first runs](#install--first-runs)
    - [Before the first run](#before-the-first-run)
    - [Try these first](#try-these-first)
  - [Skills](#skills)
  - [When to adopt this family](#when-to-adopt-this-family)
  - [Adopter contract](#adopter-contract)
  - [Status](#status)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Utilities skill family

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

Framework meta-skills — the tools you use to **build and maintain skills
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

Install just this family — one plugin, 5 skills. Framework meta-skills: author, restructure, and index your own skills.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-utilities@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

### Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

**Nothing here has to be configured.** These skills read the file below
when the project has one and fall back to a documented default when it
does not.

**Optional.** Each has a documented fallback; absent, the skill still runs.

| File | What it carries | Read by |
|---|---|---|
| [`project.md`](../../projects/_template/project.md) | Project manifest. Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. | `list-skills`, `optimize-skill`, `report-framework-issue`, `skill-reconciler`, `write-skill` |

<!-- END generated: skill-config -->

### Try these first

*Illustrative shapes, not real transcripts — your output will differ. Nothing
below sends, merges, or posts anything without you confirming it.*

**List everything installed.**

```text
/magpie-utilities:list-skills
```

![A list-skills run showing the three plugins installed here and the seven families available in the marketplace but not installed](../../assets/quickstart/families/utilities/list-skills.svg)

**Author a new skill.**

```text
/magpie-utilities:write-skill
```

![A write-skill run that drafted a new skill with conforming frontmatter, pre-flight and hard rules, and flagged the missing eval suite](../../assets/quickstart/families/utilities/write-skill.svg)

**Report a framework bug upstream.**

```text
/magpie-utilities:report-framework-issue
```

![A report-framework-issue run that searched the framework repository for an existing report, found none, and drafted one](../../assets/quickstart/families/utilities/report-framework-issue.svg)

## Skills

| Skill | Purpose | Status |
|---|---|---|
| [`write-skill`](../../skills/write-skill/SKILL.md) | Author a new framework skill or update an existing one: frontmatter, placeholder convention, injection defenses, Privacy-LLM gate-check, and validator sign-off. | stable |
| [`optimize-skill`](../../skills/optimize-skill/SKILL.md) | Optimize an existing skill by applying restructuring patterns — split an oversized `SKILL.md` into linked sibling docs, trim frontmatter, and improve eval alignment. | stable |
| [`list-skills`](../../skills/list-skills/SKILL.md) | Print a live index of every skill in this repository, grouped by family, with each skill's name and first-sentence description. | stable |
| [`skill-reconciler`](../../skills/skill-reconciler/SKILL.md) | Reconcile a skill's declared state (frontmatter, sibling docs, symlinks) against the framework's conventions and surface discrepancies with proposed fixes. | stable |

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
set, or shared infrastructure. `list-skills` and `optimize-skill` are
read-only; `write-skill` only creates or edits skill files under your control,
which you review before committing.

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
