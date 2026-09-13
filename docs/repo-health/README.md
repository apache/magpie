<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Repo-health audits — family overview](#repo-health-audits--family-overview)
  - [Install & first runs](#install--first-runs)
    - [Before the first run](#before-the-first-run)
    - [Works well with](#works-well-with)
    - [Try these first](#try-these-first)
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

> [!TIP]
> **Why this family**
> - Read-only audits that find what CI does not: unmaintained dependencies, unsafe workflow triggers, licence gaps
> - Flakes separated from real regressions, so the regression hiding among them gets found
> - Findings first, fixes second — the audit never edits a workflow or opens a PR on its own

## Install & first runs

Install just this family — one plugin, 7 skills. Read-only repository-health audits, plus fixes for what they find.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-repo-health@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

### Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

Every skill here resolves project-specific values from the adopter's
[`<project-config>/`](../../projects/_template/) directory — which is
`.apache-magpie-local/` (gitignored, yours) first, then
`.apache-magpie-overrides/` (committed, the project's).

**For yourself:** `/magpie-setup config` scaffolds and fills these locally.
Nothing is staged, nothing is committed, and it works on a repository that
has never adopted Magpie.

**For the project:** [`/magpie-setup adopt`](../setup/team-adoption.md)
commits them for every contributor, either scaffolded directly or promoted
from what you configured locally.

**Required.** Without these a skill would act on a guess, so it stops and
says which file is missing.

| File | What it carries | Read by |
|---|---|---|
| [`fix-workflow.md`](../../projects/_template/fix-workflow.md) | Fork / clone / toolchain specifics, backport-label policy, commit-trailer wording, PR scrubbing, private-PR fallback. | `audit-finding-fix` |
| [`repo-health-config.md`](../../projects/_template/repo-health-config.md) | Per-skill switches: deprecated runner labels, zizmor rule classes, dependency managers, SPDX expression, flaky-test thresholds. | `dependency-audit`, `flaky-test-triage`, `license-compliance-audit`, `workflow-security-audit` |
| [`runtime-invocation.md`](../../projects/_template/runtime-invocation.md) | Build prerequisite, run-a-single-file recipe, stream-capture conventions, network/dependency handling. | `audit-finding-fix` |

<!-- END generated: skill-config -->

<!-- BEGIN generated: companion-skills (tools/dev/check-companion-skills.py --fix) -->

### Works well with

Third-party packages, none of them required: this family works with none of
them installed, and Magpie neither bundles nor depends on any. They are named
because they are what a maintainer goes looking for next, and because the
answer differs by agent.

**[Aikido Security](https://www.aikido.dev/)** — Aikido

SAST, secrets and infrastructure-as-code scanning surfaced in the session.

*With this family:* Covers the infrastructure-as-code surface that workflow-security-audit does not read.

Available on **Claude Code** only.

**[Claude Security](https://code.claude.com/docs/en/claude-security)** — Anthropic

A multi-agent vulnerability scan of your own repository, run inside the session; each finding carries a severity, a CWE category and reproduction steps, and the ones you pick become patch files you review before applying.

*With this family:* The audits here read dependencies, workflows and licences. This reads the project's own code, which none of them do.

Available on **Claude Code** only.

Claude Code only: it drives subagents and a scan workflow that Agent Plugins 1.0 has no component for. Listed with its harness named rather than presented as the answer for everyone.

Install commands per agent are in
[**Companion skill packages**](../setup/companion-skills.md).

<!-- END generated: companion-skills -->

### Try these first

*Illustrative shapes, not real transcripts — your output will differ. Nothing
below sends, merges, or posts anything without you confirming it.*

**Audit dependencies for CVEs.**

```text
/magpie-repo-health:dependency-audit
```

![A dependency-audit run grouping findings into outdated-with-a-fix, unmaintained, and pinned-but-unused, having upgraded nothing](../../assets/quickstart/families/repo-health/dependency-audit.svg)

**Audit the Actions workflows.**

```text
/magpie-repo-health:workflow-security-audit
```

![A workflow-security-audit run: one failure where a workflow runs untrusted code with write permissions, two warnings about pinning and permissions, and nine clean files](../../assets/quickstart/families/repo-health/workflow-security-audit.svg)

**Find the flaky tests.**

```text
/magpie-repo-health:flaky-test-triage
```

![A flaky-test-triage run separating two genuine flakes from a real regression that had been hiding among them](../../assets/quickstart/families/repo-health/flaky-test-triage.svg)

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

The shape of `repo-health-config.md`, which the table under
[*Before the first run*](#before-the-first-run) links:

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
