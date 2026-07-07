<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [New project — TODO: replace with `<Project Name>`](#new-project--todo-replace-with-project-name)
  - [What each file is for](#what-each-file-is-for)
    - [Authoritative manifest (fill this in first)](#authoritative-manifest-fill-this-in-first)
    - [Release state](#release-state)
    - [Scope + product mapping](#scope--product-mapping)
    - [Security-model references](#security-model-references)
    - [CVE-allocation mechanics](#cve-allocation-mechanics)
    - [Remediation workflow](#remediation-workflow)
    - [Editorial + reporter-facing](#editorial--reporter-facing)
    - [Contributor growth](#contributor-growth)
    - [Issue management](#issue-management)
    - [Repo-health audits](#repo-health-audits)
    - [PR triage and review](#pr-triage-and-review)
    - [External skill sources](#external-skill-sources)
  - [Recommended setup order](#recommended-setup-order)
  - [Checklist after copying](#checklist-after-copying)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# New project — TODO: replace with `<Project Name>`

Skeleton directory for a new project under this framework. **Do not
edit the template in place**; copy it to `projects/<name>/` and fill
in every `TODO` placeholder:

```bash
# From the repo root:
cp -R projects/_template projects/<name>
$EDITOR projects/<name>/project.md
grep -rn TODO projects/<name>     # work through the remaining TODOs
```

The `_template` prefix keeps this directory out of the way of the
active-project resolver (the skills only load `projects/<active>/`,
so a directory that starts with `_` is never accidentally picked up).

## What each file is for

Once you have copied the template into `<project-config>/` in your
tracker repo, update this `README.md` to be your project's **file
index**. Delete the sections your project does not need and fill in
the rest.

### Authoritative manifest (fill this in first)

| File | Purpose |
|---|---|
| [`project.md`](project.md) | **Project manifest.** Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. |

### Release state

| File | Purpose |
|---|---|
| [`release-trains.md`](release-trains.md) | Active release branches, release-manager attribution per cut, rotation rosters, security-team roster. |
| [`milestones.md`](milestones.md) | Milestone naming conventions + create-and-assign recipe. |

### Scope + product mapping

| File | Purpose |
|---|---|
| [`scope-labels.md`](scope-labels.md) | Scope label → CVE product / `packageName` / collection-URL mapping. Exactly one scope label per tracker. |

### Security-model references

| File | Purpose |
|---|---|
| [`security-model.md`](security-model.md) | Authoritative URL for the project's Security Model + known-useful anchors + drafting rule. |

### CVE-allocation mechanics

| File | Purpose |
|---|---|
| [`title-normalization.md`](title-normalization.md) | Regex cascade the `security-cve-allocate` skill applies to tracker titles before pasting them into the CVE-tool allocation form. |

### Remediation workflow

| File | Purpose |
|---|---|
| [`fix-workflow.md`](fix-workflow.md) | Fork / clone / toolchain specifics, backport-label policy, commit-trailer wording, PR scrubbing, private-PR fallback. |

### Editorial + reporter-facing

| File | Purpose |
|---|---|
| [`naming-conventions.md`](naming-conventions.md) | Project-specific editorial rules. Keep only the ones that differ from the generic rules in `../../AGENTS.md`. |
| [`canned-responses.md`](canned-responses.md) | Reusable reporter-facing reply templates. |

### Contributor growth

These files configure the contributor-nomination, committer-onboarding,
and contributor-to-committer skill family. Adopters that do not use
these skills can delete this group.

| File | Purpose |
|---|---|
| [`contributor-nomination-config.md`](contributor-nomination-config.md) | Nomination-brief thresholds and assessment window. Used by `contributor-nomination`. |
| [`committer-onboarding-config.md`](committer-onboarding-config.md) | **Capability-flag vocabulary for committer intake and governance models** (`icla`/`dco`/`no-cla`; `asf-pmc`/`github-codeowners`/`maintainer-roster`). Used by `committer-onboarding`. |
| `committer-readiness.md` | Activity thresholds the `contributor-to-committer` readiness tracker compares against. Added by the `contributor-to-committer` skill. |

### Issue management

These files configure the [`issue-*`](../../skills/) skill
family — per-issue triage, pool-level reassessment, reproducer
extraction, fix drafting, and read-only stats. Adopters that do not
use a general-issue tracker (or only run the security skills) can
delete this group.

| File | Purpose |
|---|---|
| [`issue-tracker-config.md`](issue-tracker-config.md) | Tracker URL, project key, auth model, default query templates. Used by every `issue-*` skill. |
| [`runtime-invocation.md`](runtime-invocation.md) | Build prerequisite, run-a-single-file recipe, stream-capture conventions, network/dependency handling. Used by `issue-reproducer`. |
| [`reassess-pool-defaults.md`](reassess-pool-defaults.md) | Named pools for reassessment sweeps (`open-eol`, `reopened`, `stale-unresolved`, project-specific). Used by `issue-reassess`. |
| [`reproducer-conventions.md`](reproducer-conventions.md) | Evidence-package directory layout and frozen-copy discipline. Used by `issue-reproducer` and `issue-reassess-stats`. |

### Repo-health audits

These files configure the [`ci-runner-audit`](../../skills/ci-runner-audit/SKILL.md)
and [`workflow-security-audit`](../../skills/workflow-security-audit/SKILL.md)
skills and the planned `dependency-audit`, `license-compliance-audit`, and
`flaky-test-triage` skills. Adopters who do not use repo-health audits can
delete this group.

| File | Purpose |
|---|---|
| [`repo-health-config.md`](repo-health-config.md) | Per-skill switches: deprecated runner labels, zizmor rule classes, dependency managers, SPDX expression, flaky-test thresholds. Used by every `*-audit` and `flaky-test-triage` skill. |

### PR triage and review

These files configure the
[`pr-management-triage`](../../skills/pr-management-triage/SKILL.md),
[`pr-management-stats`](../../skills/pr-management-stats/SKILL.md), and
[`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md)
skills. Adopters who only use the security skills can delete these
four files; adopters running maintainer-side PR-queue management
fill them in.

| File | Purpose |
|---|---|
| [`pr-management-config.md`](pr-management-config.md) | Committers team handle, area-label prefix, project-specific labels (`ready for maintainer review`, etc.), grace windows. Used by `pr-management-triage` and `pr-management-stats`. |
| [`pr-management-triage-comment-templates.md`](pr-management-triage-comment-templates.md) | Comment-body URLs (PR quality criteria, two-stage triage rationale), AI-attribution footer wording, project display name. Used by `pr-management-triage`. |
| [`pr-management-triage-ci-check-map.md`](pr-management-triage-ci-check-map.md) | CI-check name pattern → category name + doc-URL mapping for the violations comment. Used by `pr-management-triage`. |
| [`pr-management-code-review-criteria.md`](pr-management-code-review-criteria.md) | List of project's review-criteria source files (repo-wide AGENTS.md, code-review docs, per-area AGENTS.md), security-model calibration doc, backport-branch pattern, section-anchor URLs. Used by `pr-management-code-review`. |

> Each PR-skill reads its project-specific content exclusively
> from the files listed below.  No defaults are baked into the
> framework — every adopter provides their own values in
> `<project-config>/`.  See `projects/_template/pr-management-*.md`
> for concrete examples (filled in with the Apache Airflow project's
> values, which new adopters can use as a reference when drafting
> their own configuration).

### External skill sources

| File | Purpose |
|---|---|
| [`skill-sources.md`](skill-sources.md) | **The install gate** for pulling skills/families from trusted external repos. Lists the source ids this project trusts and commits each pin. `/magpie-setup` fetches only what is listed here. Leave empty to run only in-tree framework skills. See [`docs/skill-sources/`](../../docs/skill-sources/README.md). |

## Recommended setup order

After copying the template, fill in the core project files before the
optional skill-family files:

1. Start with `project.md`, because every skill uses it to resolve
   project-scoped references.
2. Fill in `security-model.md` so security-facing workflows have an
   authoritative source.
3. Add current release details to `release-trains.md`.
4. Define tracker organization in `scope-labels.md` and `milestones.md`.
5. Prepare reporter-facing text in `canned-responses.md`.
6. Document the fix flow in `fix-workflow.md`.
7. If your project uses the issue or PR-management skill families, fill
   in the optional files they read, such as `issue-tracker-config.md`,
   `runtime-invocation.md`, `pr-management-config.md`, and
   `pr-management-code-review-criteria.md`.

Run `grep -rn TODO projects/<name>` after copying and again before
opening a pull request so no template placeholders are left behind.

## Checklist after copying

- [ ] `cp -R projects/_template projects/<name>` done.
- [ ] Every `TODO` in `project.md` resolved (grep: `grep -n TODO projects/<name>/project.md`).

**Security workflow** (delete this group if not using the security
skills):

- [ ] `scope-labels.md` lists at least one scope label (exactly-one-of rule).
- [ ] `security-model.md` points at the project's authoritative Security-Model URL.
- [ ] `release-trains.md` has at least one current release branch + its RM.
- [ ] `canned-responses.md` has at least the *"Confirmation of receiving the report"* template filled in (the `security-issue-import` skill sends this verbatim).

**PR triage and review** (delete this group if not using the
`pr-*` skills):

- [ ] `pr-management-config.md` — committers team handle and area-label prefix filled in.
- [ ] `pr-management-triage-comment-templates.md` — `<quality_criteria_url>`, `<two_stage_triage_rationale_url>`, and `<project_display_name>` filled in.
- [ ] `pr-management-triage-ci-check-map.md` — at least one CI-check pattern row filled in (or the catch-all row pointing at the project's static-checks doc).
- [ ] `pr-management-code-review-criteria.md` — at least one repo-wide review-criteria source file declared.

**Common finishers**:

- [ ] `config/active-project.md` updated to the new directory name if this working tree should target the new project.
- [ ] Root `README.md` *"Current projects"* table updated with a row for the new project + a link to this `README.md`.
- [ ] `prek run --all-files` passes.

## Cross-references

- [`../../README.md`](../../README.md) — framework-level *"Adopting the
  framework"* view + bootstrap walk-through.
- [`../../AGENTS.md`](../../AGENTS.md#placeholder-convention-used-in-skill-files) —
  the placeholder convention that lets skills resolve `<project-config>/`
  to the adopter's path at agent runtime.
