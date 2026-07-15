<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Repo-health audits — family overview](#repo-health-audits--family-overview)
  - [Current skills](#current-skills)
    - [`audit-finding-fix` (experimental)](#audit-finding-fix-experimental)
    - [`ci-runner-audit` (experimental)](#ci-runner-audit-experimental)
    - [`workflow-security-audit` (experimental)](#workflow-security-audit-experimental)
    - [`dependency-audit` (experimental)](#dependency-audit-experimental)
    - [`license-compliance-audit` (experimental)](#license-compliance-audit-experimental)
    - [`flaky-test-triage` (experimental)](#flaky-test-triage-experimental)
    - [`dependency-license-audit` (experimental)](#dependency-license-audit-experimental)
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

### `audit-finding-fix` (experimental)

Takes a single audit finding (from `ci-runner-audit`,
`workflow-security-audit`, `dependency-audit`, or
`license-compliance-audit`) and drafts a targeted fix PR: code change,
commit message, and PR description. The fix addresses exactly one finding
and includes a regression check where applicable.

Drafts only; the human committer reviews and pushes. Never modifies files
or opens PRs without explicit maintainer confirmation.

**Adopter contract**: reads `<project-config>/repo-health-config.md`
(`audit_finding_fix.pr_template`) for the PR description template and
branch-naming convention.

---

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

### `dependency-license-audit` (experimental)

Resolve the license of every direct and transitive dependency and classify
each against the project's license policy. This is distinct from the two
existing skills: `license-compliance-audit` checks the project's own
LICENSE, NOTICE, and SPDX headers (and excludes vendored code), and
`dependency-audit` checks dependencies for known vulnerabilities, not
license terms. Neither audits the licenses of the dependency tree.

Checks performed:

1. Detect the dependency manager(s) (reusing `dependency-audit`'s detection)
   and enumerate direct and transitive dependencies.
2. Resolve each dependency's declared license from ecosystem metadata
   (`pip-licenses` / PyPI, `license-checker` for npm, `cargo-deny` or
   `cargo license` for Rust, or `trivy` license scanning for multi-language).
3. Classify each result against a configured policy. The default ASF policy
   applies the three-category model: category A allowed, category B allowed in
   binary/convenience-binary form only (not in source releases), category X
   (copyleft such as GPL / AGPL / LGPL, and non-commercial terms) forbidden. Dependencies whose license
   cannot be resolved are reported as unknown.

Surfaces incompatible, forbidden, and unknown-license dependencies as a
grouped report with a proposed remedy per finding (replace, remove, or
request a relicense). Read-only; never edits a manifest or lock file.

**Adopter contract**: reads `<project-config>/repo-health-config.md`
(`dependency_license_audit`) for the policy model, explicit allow / forbid
lists, whether to include transitive dependencies, and how to treat
unknown-license dependencies.

**Note — optional dependencies are out of scope, and that is usually fine.**
The scan reports the resolved/installed dependency graph, so optional extras
and feature-gated dependencies (Python extras, npm `optionalDependencies` /
`peerDependencies`, Cargo features, Gradle `compileOnly` and feature variants,
Maven `provided`-scope deps) are not covered unless enabled at scan time. For
ASF adopters this is by design rather than a gap: a Category X dependency is
prohibited only when it is *distributed* in ASF source or a convenience
binary. An optional, non-distributed Category X dependency that merely
supports an optional feature (or a build-time-only tool) is explicitly
permitted, so the default scan already covers what the policy cares about. If
a maintainer wants the full dependency inventory regardless of distribution,
enable all extras and features (for example `uv sync --all-extras
--all-groups`, `cargo license --all-features`) or audit a full-universe lock
file. See the "may not be distributed" guidance in the ASF resolved-licenses
policy: <https://www.apache.org/legal/resolved.html>.

---

## Status

**Experimental.** All seven skills shipped. No adopter-pilot evaluation
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

  dependency_license_audit:
    # License policy model: "asf" applies the ASF category A/B/X model;
    # "allowlist" uses allowed_licenses only.
    policy: asf
    # SPDX expressions always allowed, regardless of policy.
    allowed_licenses: [Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC]
    # SPDX expressions always forbidden (category X).
    forbidden_licenses: [GPL-2.0-only, GPL-3.0-only, AGPL-3.0-only, LGPL-3.0-only]
    # Include transitive dependencies (default true).
    include_transitive: true
    # What to do when a dependency's license cannot be resolved: flag | ignore.
    unknown_license_action: flag
```

---

## Cross-references

- [`docs/modes.md` § Triage](../modes.md#triage) — mode taxonomy; repo-health
  skills are listed in the Triage table.
- [`tools/spec-loop/specs/repo-health-family.md`](../../tools/spec-loop/specs/repo-health-family.md)
  — functional spec: acceptance criteria, validation commands, and known gaps.
- [`tools/spec-loop/specs/triage-mode.md`](../../tools/spec-loop/specs/triage-mode.md)
  — parent spec that identified the family gap.
