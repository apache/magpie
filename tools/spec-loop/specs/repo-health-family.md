<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Repo-health audits
status: experimental
kind: feature
mode: Triage
source: >
  MISSION.md § Technical scope (Triage). triage-mode.md Known Gaps
  ("Repo-health audits are a one-off with no family around them;
  ci-runner-audit is a standalone read-only audit"). Family design in
  docs/repo-health/README.md. ci-runner-audit is the first shipped member.
acceptance:
  - Every repo-health skill is read-only or proposes-then-confirms; none
    modifies workflow files, runner configs, or dependency files without
    human confirmation.
  - ci-runner-audit validates under skill-and-tool-validate and ships an
    eval suite.
  - docs/modes.md Triage table lists each shipped repo-health skill.
---

# Repo-health audits

## What it does

Surface repository-level health signals a maintainer would otherwise detect
by hand: obsolete runner labels, Actions workflow security vulnerabilities,
stale or vulnerable dependencies, license/NOTICE compliance drift, and
flaky-test patterns. Every skill in the family produces a structured report
and proposes remedies for human review; no skill applies a change without
explicit maintainer confirmation.

The family extends the Triage mode's classify-and-propose discipline to
repository maintenance. The canonical sequence is: fetch a bounded snapshot
of the target artefacts → classify each against a rule set → present a
grouped, prioritised report → wait for confirmation before any write.

## Where it lives

- Skills (four shipped): `ci-runner-audit` (obsolete GitHub-hosted runner
  labels and macOS architecture mismatches), `workflow-security-audit`
  (zizmor-backed Actions security findings — injection, excessive
  permissions, unpinned external actions, fork-secret leaks),
  `dependency-audit` (known-vulnerable / outdated dependencies), and
  `license-compliance-audit` (LICENSE presence, NOTICE completeness, and
  SPDX-header consistency). Each reads across one repo, an explicit set,
  one Apache project's repos, or the full Apache GitHub org, is read-only
  (no workflow file, manifest, lock file, or source file is modified), and
  ships `mode: Triage` + `experimental` with an eval suite.
- Design docs: `docs/repo-health/README.md` — family overview, remaining
  candidate skill (flaky-test-triage), and the planned adopter-config
  scaffold.
- Planned adopter config: `projects/_template/repo-health-config.md` —
  per-skill switches (deprecated-runner families, zizmor rule classes,
  dependency-manager selection, SPDX expression, flaky-test window).
  Lands in a separate build item once at least one candidate skill reaches
  the planning stage.

## Behaviour & contract

- **Read-only by default.** The core loop of every repo-health skill is
  read → classify → present. State changes (filing a tracking issue,
  opening an update PR) are explicit proposals the maintainer confirms;
  no skill performs an unconfirmed write to the upstream repo, the
  tracker, or any config file.
- **Point-in-time snapshot.** Each run produces a bounded audit report —
  not a continuous monitor. Re-runs extend or replace the snapshot;
  no incremental state is persisted between runs.
- **Authenticated read only.** Skills use `gh api` (read-scoped) for
  private repos; no write OAuth scopes are requested or used.
- **One skill, one rule family.** Each candidate skill targets a distinct
  maintenance concern (runner labels, workflow security, dependency
  freshness, license compliance, test stability). Skills do not share
  intermediate state, so each runs independently.

## Out of scope

- **Applying changes.** Updating a workflow file, opening a dependency-bump
  PR, or correcting a license header are maintainer actions. Skills propose;
  humans act.
- **Continuous monitoring.** That is a CI / GitHub Actions job responsibility.
  Each skill run is a triggered, bounded audit.
- **Auto-merge of housekeeping changes.** Runner-label fixes and NOTICE
  updates are eligible for Auto-merge only once that mode is on; the
  repo-health skills never trigger a merge autonomously.
- **Security-class vulnerabilities.** CVE-rated dependency issues flow
  through the security-issue lifecycle
  ([security-issue-lifecycle.md](security-issue-lifecycle.md)); the
  `dependency-audit` candidate handles non-CVE dependency hygiene.

## Acceptance criteria

1. Every repo-health skill is read-only or proposes-then-confirms; no skill
   modifies workflow files, dependency manifests, or source files without
   human confirmation.
2. `ci-runner-audit` validates under `skill-and-tool-validate` and ships an
   eval suite under `tools/skill-evals/evals/ci-runner-audit/`.
3. `docs/modes.md` Triage table carries each shipped repo-health skill.

## Validation

```bash
test -f .claude/skills/magpie-ci-runner-audit/SKILL.md
test -f .claude/skills/magpie-workflow-security-audit/SKILL.md
test -f .claude/skills/magpie-dependency-audit/SKILL.md
test -f .claude/skills/magpie-license-compliance-audit/SKILL.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **Family is four skills deep.** `ci-runner-audit`,
  `workflow-security-audit`, `dependency-audit`, and
  `license-compliance-audit` have shipped (read-only, `experimental`, each
  with an eval suite). One candidate remains designed in
  `docs/repo-health/README.md`: `flaky-test-triage`. It is a separate build
  item, sequenced after the shipped members' pilot evaluation confirms the
  family shape.
- **No adopter-config scaffold yet.** `projects/_template/repo-health-config.md`
  is planned alongside the first candidate skill; the keys are sketched in
  `docs/repo-health/README.md § Adopter contract`.
- **`ci-runner-audit` eval suite exists but no adopter pilot has run.**
  The skill is `experimental`; behaviour may change as cross-org run
  volumes expose edge cases in runner-label classification.
