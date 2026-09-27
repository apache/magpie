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
    - [Archive system](#archive-system)
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

This fixture shows the **minimal per-project configuration** a real
independent adopter would declare — only values that override or extend the
[`organizations/independent/`](../../organizations/independent/) defaults.
Org-level values (`cve_authority`, `forwarders`, `mail_provider`,
`project_metadata`, and most of `archive_system` and `release_process`) are
inherited from that manifest and not repeated here. See
[`projects/_template/project.md`](../../plugins/magpie-setup/templates/project.md) for the full
schema and field descriptions.

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

The blocks below declare only **per-project values** — overrides and
extensions of what `organizations/independent/organization.md` already
provides. Inherited keys (`forwarders`, `mail_provider`, `project_metadata`,
and the base CVE/governance/inbox defaults) are omitted; the framework
resolves them from the organization manifest automatically.

### CVE authority

```yaml
cve_authority:
  # Override the independent-org 2-stop state machine: Velox uses MITRE's
  # extended 4-stop sequence and polls for publication rather than waiting
  # for manual notification.
  states: [allocated, review-ready, publish-ready, public]
  publication_propagation: poll
```

### Governance

```yaml
governance:
  # Per-project: escalation handle and public roster URL.
  escalation_contact: "@velox-lead"
  roster_url: https://github.com/orgs/velox-community/people
```

### Security inbox

```yaml
security_inbox:
  # Per-project: the concrete GHSA inbox URL for this repo.
  address: https://github.com/velox-community/velox-stream/security/advisories
```

### Archive system

```yaml
archive_system:
  # Per-project: where public advisories and release notes surface.
  advisory_publication_signal_url: https://github.com/velox-community/velox-stream/releases
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
  # Override: PyPI only (independent-org default is []).
  artifact_registries: [pypi]

  # Per-project: this project has no overdue milestones to track.
  stale_milestones: []

  # Per-project: newsfragments tool.
  newsfragments:
    enabled: true
    tool: towncrier
```

### Roster

```yaml
roster:
  # Per-project: name → handle map and release-manager list.
  # roster.source is inherited from organizations/independent (roster-file).
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
