<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Velox Stream — project manifest (non-ASF fixture)](#velox-stream--project-manifest-non-asf-fixture)
  - [Identity](#identity)
  - [Repositories](#repositories)
  - [Mailing lists](#mailing-lists)
  - [Tools enabled](#tools-enabled)
  - [Security workflow configuration](#security-workflow-configuration)
    - [CVE authority](#cve-authority)
    - [Governance](#governance)
    - [Security inbox](#security-inbox)
    - [Forwarders](#forwarders)
    - [Mail provider](#mail-provider)
    - [Archive system](#archive-system)
    - [Project metadata](#project-metadata)
    - [Tracker](#tracker)
    - [Scope detection](#scope-detection)
    - [Release process](#release-process)
    - [Roster](#roster)
    - [Product](#product)
  - [Pointers to sibling files](#pointers-to-sibling-files)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Velox Stream — project manifest (non-ASF fixture)

This is a **fictional, non-ASF project** used as a test fixture to verify
that the framework's skills work without any ASF-specific configuration.
See [`README.md`](README.md) for the fixture's purpose.

## Identity

| Key | Value |
|---|---|
| `organization` | `independent` ([`organizations/independent/`](../../organizations/independent/)) — the no-formal-governing-body baseline. |
| `project_name` | Velox Stream |
| `vendor` | Velox Community |
| `short_name` | velox-stream |
| `product_family_url` | https://velox-stream.example.io/ |

This fixture **spells out every workflow knob explicitly** below, even
the ones it would otherwise inherit from `organizations/independent/`,
so the worked example is self-contained and the values are visible at a
glance. A real adopter would omit the inherited keys and declare only
its per-project values (see [`projects/_template/project.md`](../_template/project.md)).

## Repositories

| Key | Value | Purpose |
|---|---|---|
| `tracker_repo` | velox-community/velox-stream-security | Private security tracker |
| `tracker_repo_url` | https://github.com/velox-community/velox-stream-security | |
| `tracker_default_branch` | main | Default PR target |
| `tracker_project_board_url` | (none — no project board) | |
| `upstream_repo` | velox-community/velox-stream | Public codebase |
| `upstream_repo_url` | https://github.com/velox-community/velox-stream | |
| `upstream_default_branch` | main | |
| `upstream_contributing_docs_url` | https://github.com/velox-community/velox-stream/blob/main/CONTRIBUTING.md | |
| `upstream_security_policy_url` | https://github.com/velox-community/velox-stream/security/policy | |

## Mailing lists

None. This project uses GitHub Discussions for community communication
and has no public mailing lists.

| Key | Value | Notes |
|---|---|---|
| `security_list` | (none — uses GHSA intake) | Security reports via GitHub Security Advisories |
| `dev_list` | (none — uses GitHub Discussions) | |
| `announce_list` | (none — uses GitHub Releases) | |

## Tools enabled

| Capability | Tool | Notes |
|---|---|---|
| Issue tracking + source control | `github` | `velox-community/velox-stream` |
| Security advisory intake | `ghsa` | GitHub Security Advisories (no mail backend) |
| CVE allocation + record mgmt | `mitre-form` | Direct MITRE submission form |
| Distribution | `github-releases` | No `dist.apache.org` or `closer.lua` |

## Security workflow configuration

### CVE authority

```yaml
cve_authority:
  # Non-ASF adopter: direct MITRE CNA submission form, not Vulnogram.
  tool: mitre-form

  # Front-door allocation URL — MITRE's request form.
  allocate_url: https://cveform.mitre.org/

  # Record URL template — public cve.org record.
  record_url_template: https://www.cve.org/CVERecord?id=<CVE-ID>

  # No "source tab" equivalent; set to null.
  source_tab_url_template: null

  # No allocation email preview; set to null.
  email_preview_url_template: null

  # MITRE state machine maps to the generic 4-stop sequence.
  states: [allocated, review-ready, publish-ready, public]

  # MITRE notifies by email; poll for public propagation.
  publication_propagation: poll

  # MITRE does not auto-email on allocation.
  emits_allocation_email: false

  # Review happens in a private GitHub discussion thread, not a mailing list.
  reviewer_channel: github-pr
```

### Governance

```yaml
governance:
  # Non-ASF: any security team member can allocate a CVE.
  cve_allocation_gate: security-team-member

  # Tracker label for security-team-member gate.
  gate_label: "security-team"

  # No formal release-vote gate.
  release_vote_gating: false

  # No private mailing list; use GitHub team DMs or a private channel.
  private_governance_list: null

  # Escalation contact (GitHub handle of the project lead).
  escalation_contact: "@velox-lead"

  # Public maintainer roster on GitHub.
  roster_url: https://github.com/orgs/velox-community/people
```

### Security inbox

```yaml
security_inbox:
  # Non-ASF: GitHub Security Advisories (GHSA private reports), not email.
  kind: ghsa-inbox

  # GHSA inbox URL.
  address: https://github.com/velox-community/velox-stream/security/advisories

  # No foundation-level security address.
  foundation_security_address: null

  # No forwarder/relay layer.
  has_forwarder_relay: false

  # GHSA uses the platform's own notification channel, not a list filter.
  list_filter_query: null
```

### Forwarders

```yaml
forwarders:
  # Non-ASF: no forwarder/relay layer.
  enabled: []
```

### Mail provider

```yaml
mail_provider:
  # Non-ASF: no mail backend; security intake is entirely via GHSA.
  primary: none
  fallback: none
```

### Archive system

```yaml
archive_system:
  # Non-ASF: no public mailing-list archive. Announcements go on
  # GitHub Releases.
  kind: none
  list_domain: null
  search_url_template: null
  api_query_url_template: null
  advisory_publication_signal_url: https://github.com/velox-community/velox-stream/releases
```

### Project metadata

```yaml
project_metadata:
  # Non-ASF: no apache-projects-mcp. Roster is supplied by maintainers
  # via the release-trains.md file.
  kind: none

  # Not a pre-flight prerequisite (no ASF roster service available).
  mandatory: false

  install_source: null
```

### Tracker

```yaml
tracker:
  platform: github
  board: none
  visibility: private
  reporter_has_access: false
  project_board_enabled: false
  skill_url_template: "https://github.com/velox-community/velox-stream-security/blob/main/.claude/skills/<skill>/SKILL.md"

  body_fields:
    cve_link: "CVE link"
    mailing_thread: "Security advisory URL"
    affected_versions: "Affected versions"

  labels:
    security_marker: "security"
    needs_triage: "needs triage"
    pr_open: "pr created"
    pr_merged: "pr merged"
    cve_allocated: "cve allocated"
    not_cve_worthy: "not cve worthy"
    rejections_ledger: "rejections-ledger"
```

### Scope detection

```yaml
scope_detection:
  # Single-artifact project; no scope sub-products.
  enabled: false
  labels: {}
```

### Release process

```yaml
release_process:
  # Non-ASF: RM lookup from a roster file only; no wiki or mailing-list thread.
  release_manager_lookup_cascade:
    - kind: roster_file
      path: "release-trains.md"

  # Artifacts published on PyPI only (no ArtifactHub / Helm chart).
  artifact_registries: [pypi]

  stale_milestones: []

  newsfragments:
    enabled: true
    tool: towncrier
```

### Roster

```yaml
roster:
  # Source of truth: a checked-in roster file.
  source: roster-file:release-trains.md

  bare_name_handles:
    "Alex": "@alex-velox"
    "Robin": "@robin-velox"

  release_managers:
    - "@alex-velox"
```

### Product

```yaml
product:
  name: velox-stream
  package_name: velox-stream
  code_pointer_path_prefix: "^src/"
  subject_prefix_strip:
    - "[SECURITY]"
    - "[Security Report]"
    - "Re:"
    - "Fwd:"
    - "velox-stream:"
  affected_version_extract_prefix: "velox-stream"
```

## Pointers to sibling files

- [`issue-tracker-config.md`](issue-tracker-config.md) — general-issue tracker.
- [`stale-sweep-config.md`](stale-sweep-config.md) — stale-sweep thresholds.
