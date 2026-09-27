<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Repo-health audit configuration](#repo-health-audit-configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Repo-health audit configuration

Per-skill switches for the repo-health audit family. Copy this file into
your `<project-config>/` directory and fill in the `TODO` values. Skills
in this family (`ci-runner-audit`, `workflow-security-audit`,
`dependency-audit`, `license-compliance-audit`, `flaky-test-triage`, and
`dependency-license-audit`) read from this file at run time.

See `docs/repo-health/README.md` for a full description of each skill
and adopter-contract details.

---

```yaml
repo_health:

  # ---------------------------------------------------------------------------
  # ci-runner-audit — obsolete GitHub-hosted runner labels and macOS arch
  # mismatches.  Consumed by: ci-runner-audit (experimental).
  # ---------------------------------------------------------------------------
  ci_runner_audit:

    # Runner label names the skill treats as obsolete/retired.
    # Default: the GitHub-deprecated label list below.
    # Override when: your project uses custom runners whose labels should also
    # be flagged (add them here), or you want to suppress a label from the
    # default list (remove it).
    deprecated_runner_labels:
      - ubuntu-18.04
      - ubuntu-20.04
      - windows-2019
      - macos-11
      - macos-12

    # Additional repositories to audit alongside the project's primary repos.
    # Use `owner/repo` form. Leave empty to audit only the repos listed in
    # project.md (upstream_repo, tracker_repo).
    # TODO: add extra repos if needed, e.g. ["apache/foo-site", "apache/foo-client"]
    extra_repos: []

  # ---------------------------------------------------------------------------
  # workflow-security-audit — GitHub Actions security issues surfaced by
  # zizmor.  Consumed by: workflow-security-audit (experimental).
  # ---------------------------------------------------------------------------
  workflow_security_audit:

    # zizmor finding classes to enable. All four are on by default.
    # Remove a class to suppress that finding category for this project.
    # ASF default: all enabled (injection and fork-secrets are high-severity;
    # excessive-permissions and unpinned-actions are medium-severity).
    # Override when: the project intentionally uses floating action references
    # (e.g. in non-production automation) or has a justified write permission.
    enabled_rules:
      - injection            # untrusted event data interpolated into run: steps
      - excessive-permissions  # write-all or unneeded write scopes
      - unpinned-actions     # @tag or @branch references instead of SHA pins
      - fork-secrets         # secrets accessible from pull_request_target

    # Additional repositories to audit beyond project.md → upstream_repo.
    # TODO: add extra repos if needed, e.g. ["apache/foo-site"]
    extra_repos: []

  # ---------------------------------------------------------------------------
  # dependency-audit — known-vulnerability check on direct + transitive deps.
  # Consumed by: dependency-audit (experimental).
  # ---------------------------------------------------------------------------
  dependency_audit:

    # Dependency managers in use. Selects the audit tool adapter.
    # Allowed values: pip, npm, cargo, maven, gradle
    # TODO: set to your project's dependency managers, e.g. [pip] or [npm, pip]
    managers:
      - pip

    # Minimum severity level to include in the report.
    # Allowed values: low, medium, high, critical
    # Default: medium (suppress low-signal informational hits).
    min_severity: medium

  # ---------------------------------------------------------------------------
  # license-compliance-audit — SPDX header and NOTICE compliance check.
  # Consumed by: license-compliance-audit (experimental).
  # ---------------------------------------------------------------------------
  license_compliance_audit:

    # Required SPDX license expression for every source file under
    # source_paths. Must be a valid SPDX expression string.
    # TODO: set to your project's license, e.g. "Apache-2.0"
    required_spdx_expression: "TODO: Apache-2.0"

    # Source paths to audit for license headers (relative to upstream repo root).
    # TODO: set to your project's source directories, e.g. [src/, lib/]
    source_paths:
      - "TODO: src/"

    # Paths to skip — test fixtures, vendored code, generated files, etc.
    # TODO: add any paths that legitimately lack headers (or have different ones)
    skip_paths:
      - "TODO: tests/fixtures/"

  # ---------------------------------------------------------------------------
  # flaky-test-triage — intermittent test failure detection from CI run history.
  # Consumed by: flaky-test-triage (experimental).
  # ---------------------------------------------------------------------------
  flaky_test_triage:

    # Audit window in days. The skill scans CI run history over this period.
    # Default: 30 days (enough signal without fetching unbounded history).
    window_days: 30

    # Minimum failure-rate fraction to flag a job as candidate flaky.
    # A job that fails 10% of the time or more is flagged by default.
    # Override when: your project has a higher noise floor and 10% is too noisy.
    failure_rate_threshold: 0.10

    # Job-name glob patterns to include in the analysis.
    # Leave empty to analyse all jobs in the CI run.
    # TODO: narrow to the jobs most prone to flakiness if needed.
    include_patterns: []

    # Job-name glob patterns to exclude (known-always-failing or skipped jobs).
    # TODO: add patterns for jobs that are legitimately unstable but not flaky.
    exclude_patterns: []

  # ---------------------------------------------------------------------------
  # dependency-license-audit — license classification of direct + transitive
  # dependencies against a policy.  Consumed by: dependency-license-audit.
  # ---------------------------------------------------------------------------
  dependency_license_audit:

    # License policy model.
    #   asf       — apply the ASF three-category model (A allowed, B allowed
    #               in binary/convenience-binary form only, X forbidden).
    #   allowlist — allow only the SPDX expressions in allowed_licenses below.
    # Default: asf.
    policy: asf

    # SPDX expressions always treated as allowed, regardless of policy.
    # Override when: your project permits additional permissive licenses.
    allowed_licenses:
      - Apache-2.0
      - MIT
      - BSD-2-Clause
      - BSD-3-Clause
      - ISC

    # SPDX expressions always treated as forbidden (ASF category X).
    # Override when: your project has an exception for a specific dependency.
    forbidden_licenses:
      - GPL-2.0-only
      - GPL-3.0-only
      - AGPL-3.0-only
      - LGPL-3.0-only

    # Audit transitive dependencies, not just direct ones. Default: true.
    include_transitive: true

    # How to treat a dependency whose license cannot be resolved.
    # Allowed values: flag (report as unknown), ignore.
    # Default: flag.
    unknown_license_action: flag
```
