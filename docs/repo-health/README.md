<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Repo-health audits — family overview](#repo-health-audits--family-overview)
  - [Current skills](#current-skills)
    - [`ci-runner-audit` (experimental)](#ci-runner-audit-experimental)
    - [`workflow-security-audit` (experimental)](#workflow-security-audit-experimental)
    - [`dependency-audit` (experimental)](#dependency-audit-experimental)
    - [`license-compliance-audit` (experimental)](#license-compliance-audit-experimental)
    - [`flaky-test-triage` (experimental)](#flaky-test-triage-experimental)
  - [Status](#status)
  - [Adopter contract](#adopter-contract)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Repo-health audits — family overview

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

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

### `workflow-security-audit` (experimental)

Runs [`zizmor`](https://woodruffw.github.io/zizmor/) — the GitHub Actions
security scanner already wired into the framework's own pre-commit suite —
across one repository, an explicit repository set, or a whole GitHub org and
surfaces findings for human review.

Finding classes surfaced:

- **Injection vulnerabilities** — `run:` steps consuming
  `${{ github.event.* }}` or `${{ github.head_ref }}` in untrusted contexts.
- **Excessive permissions** — `permissions: write-all` or unnecessary `write`
  scopes at the workflow or job level.
- **Unpinned external actions** — floating `@main`, `@master`, or tag-only
  references instead of a commit SHA.
- **Self-hosted runner fork-secret leaks** — secrets reachable from PRs
  submitted by fork contributors via self-hosted runners.

Output is a grouped, prioritised finding report. Read-only; the skill never
edits workflow files, opens PRs, or posts comments.

**Adopter contract**: reads `<project-config>/repo-health-config.md`
(`workflow_security_audit.enabled_rules`) to select which rule classes to
enable. All classes are enabled by default.

---

### `dependency-audit` (experimental)

Detects the project's dependency manager(s), runs the appropriate audit
tool (`pip-audit`, `npm audit`, `cargo audit`, or `trivy`), and surfaces
patchable vulnerability findings grouped by severity for maintainer triage.

- Works against one repository (`--repo owner/name`) or a local checkout
  (`--path /path/to/checkout`).
- Differentiates CVE-rated vulnerabilities (those with a CVE ID) from
  advisory-only findings.
- Proposes one upgrade per affected dependency; never modifies manifests,
  lock files, or opens update PRs autonomously.

**Adopter contract**: reads `<project-config>/repo-health-config.md`
(`dependency_audit.managers`) to select the dependency manager adapter(s).

---

### `license-compliance-audit` (experimental)

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

### `flaky-test-triage` (experimental)

Parse GitHub Actions run history for a named repo over a configurable window,
compute per-job failure rates (differentiating consistent failures from
intermittent ones), and produce a prioritised triage list: jobs failing
above a configurable threshold that are likely flaky rather than
deterministically broken.

Signals used: run outcome (`success` / `failure`), re-run count on the same
SHA, job-name patterns across runs. No test code is modified.

**Adopter contract**: reads `<project-config>/repo-health-config.md` for
the audit window, the failure-rate threshold, and which test-name patterns
to include or exclude.

---

## Status

**Experimental.** All five skills shipped. No adopter-pilot evaluation
has run end-to-end yet; shape may change between framework versions.

To provide pilot feedback, copy
[`docs/pilot-report-template.md`](../pilot-report-template.md) into your
project notes, fill in each section, and optionally validate the filled-in
report with:

```bash
uv run --project tools/pilot-report-validator pilot-report-validate <your-report.md>
```

## Adopter contract

`projects/_template/repo-health-config.md` provides the per-project
configuration scaffold for all repo-health skills. Copy it into your
`<project-config>/` directory and fill in the `TODO` fields for each skill
you enable:

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

---

## Cross-references

- [`docs/modes.md` § Triage](../modes.md#triage) — mode taxonomy; repo-health
  skills are listed in the Triage table.
- [`tools/spec-loop/specs/repo-health-family.md`](../../tools/spec-loop/specs/repo-health-family.md)
  — functional spec: acceptance criteria, validation commands, and known gaps.
- [`tools/spec-loop/specs/triage-mode.md`](../../tools/spec-loop/specs/triage-mode.md)
  — parent spec that identified the family gap.
