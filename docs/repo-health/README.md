<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Repo-health audits — family overview](#repo-health-audits--family-overview)
  - [Current skills](#current-skills)
    - [`ci-runner-audit` (experimental)](#ci-runner-audit-experimental)
  - [Candidate skills (not yet built)](#candidate-skills-not-yet-built)
    - [`workflow-security-audit` (proposed)](#workflow-security-audit-proposed)
    - [`dependency-audit` (proposed)](#dependency-audit-proposed)
    - [`license-compliance-audit` (proposed)](#license-compliance-audit-proposed)
    - [`flaky-test-triage` (proposed)](#flaky-test-triage-proposed)
  - [Adopter contract (planned)](#adopter-contract-planned)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Repo-health audits — family overview

Read-only agent-assisted audits that surface repository maintenance signals
a human would otherwise have to detect by hand: runner label obsolescence,
Actions workflow security issues, stale or vulnerable dependencies,
license/NOTICE drift, and flaky-test patterns. Every skill in this family
produces a human-readable report and proposes remedies; applying any change
is the maintainer's action.

The family lives under `mode: Triage` in the framework taxonomy — the same
classify-and-propose discipline the security and PR-management triage skills
follow. See [`docs/modes.md` § Triage](../modes.md#triage).

---

## Current skills

### `ci-runner-audit` (experimental)

Reads every GitHub Actions workflow file across one repo, a named set, one
Apache project's repos, or the full Apache GitHub org and surfaces two
classes of issue:

1. **Obsolete runner labels** — `ubuntu-18.04`, `ubuntu-20.04`, `windows-2019`,
   and other GitHub-deprecated hosted-runner label strings that silently fall
   back to a later image or will soon break.
2. **macOS architecture mismatches** — a workflow step targeting an `arm64`
   macOS runner that invokes an `x86_64`-only tool or vice versa.

Output is a markdown audit report grouped by repo and by issue class.
Read-only; no workflow files are modified.

---

## Candidate skills (not yet built)

These are enumerated from the triage-mode.md Known Gaps. Each will become
its own build item once the family shape is confirmed through
`ci-runner-audit` pilot evaluations.

### `workflow-security-audit` (proposed)

Run [`zizmor`](https://woodruffw.github.io/zizmor/) — the GitHub Actions
security scanner already wired into the framework's own pre-commit suite —
across one repo or a named set and surface findings for human review.

Proposed finding classes:

- Injection vulnerabilities (`run:` steps using `${{ github.event.* }}` or
  `${{ github.head_ref }}` in untrusted contexts)
- Excessive permissions (`permissions: write-all` or unnecessary `write`
  scopes on workflow-level or job-level grants)
- Unpinned external actions (floating `@main`, `@master`, or tag-only
  references instead of a commit SHA)
- Self-hosted runner scope leakage (secrets available to PRs from forks)

Each finding class maps to a concise prose description and a suggested
remediation (scope reduction, SHA pinning, `${{ env.SAFE_VAR }}` pattern).

**Adopter contract**: reads `<project-config>/repo-health-config.md`
(planned) for which rule classes to enable and which repos to audit.

### `dependency-audit` (proposed)

Check direct and transitive dependencies for known vulnerabilities (via
`pip-audit` / `npm audit` / `trivy` depending on the project's language
stack) and surface those that have available patches. One finding per
dependency, formatted for maintainer triage. Does not open update PRs
autonomously — proposes one per affected dependency.

**Adopter contract**: reads `<project-config>/repo-health-config.md` for
the dependency manager and audit tool to use.

### `license-compliance-audit` (proposed)

Verify that:

1. Every source file under a configured path carries the project's required
   SPDX-License-Identifier header line.
2. The `LICENSE` file matches the declared SPDX expression.
3. The `NOTICE` file lists every bundled dependency that its license
   requires to appear in attribution notices.

Surfaces discrepancies as a structured report (file path, issue class,
suggested correction) without modifying any file.

**Adopter contract**: reads `<project-config>/repo-health-config.md` for
the required SPDX expression and which source paths to audit.

### `flaky-test-triage` (proposed)

Parse GitHub Actions run history for a named repo over a configurable window,
compute per-test failure rates (differentiating consistent failures from
intermittent ones), and produce a prioritised triage list: tests failing
above a configurable threshold that are likely flaky rather than
deterministically broken.

Signals used: run outcome (`success` / `failure`), re-run count on the same
SHA, test-name patterns across runs. No test code is modified.

**Adopter contract**: reads `<project-config>/repo-health-config.md` for
the audit window, the failure-rate threshold, and which test-name patterns
to include or exclude.

---

## Adopter contract (planned)

A future `projects/_template/repo-health-config.md` will declare per-skill
switches:

```yaml
repo_health:
  ci_runner_audit:
    # Runner label families to flag. Defaults to the GitHub-deprecated list.
    deprecated_runner_labels: [ubuntu-18.04, ubuntu-20.04, windows-2019]
    # Repos to audit; leave empty to audit only the project's own repos.
    extra_repos: []

  workflow_security_audit:
    # zizmor rule classes to enable (all enabled by default).
    enabled_rules: [injection, excessive-permissions, unpinned-actions, fork-secrets]

  dependency_audit:
    # Dependency manager(s) in use. Selects the audit tool adapter.
    # Allowed values: pip, npm, cargo, maven, gradle
    managers: [pip]

  license_compliance_audit:
    # Required SPDX expression for all source files.
    required_spdx_expression: "Apache-2.0"
    # Source paths to audit (relative to upstream repo root).
    source_paths: [src/, lib/]
    # Paths to skip (test fixtures, vendored code, etc.).
    skip_paths: [tests/fixtures/, vendor/]

  flaky_test_triage:
    # Audit window in days.
    window_days: 30
    # Minimum failure rate (fraction) to flag a test as candidate flaky.
    failure_rate_threshold: 0.1
```

The config file will land in a separate build item once at least one
candidate skill reaches the planning stage.

---

## Cross-references

- [`docs/modes.md` § Triage](../modes.md#triage) — mode taxonomy; repo-health
  skills are listed in the Triage table.
- [`tools/spec-loop/specs/repo-health-family.md`](../../tools/spec-loop/specs/repo-health-family.md)
  — functional spec: acceptance criteria, validation commands, and known gaps.
- [`tools/spec-loop/specs/triage-mode.md`](../../tools/spec-loop/specs/triage-mode.md)
  — parent spec that identified the family gap.
