<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`tools/security-tracker/`](#toolssecurity-tracker)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/security-tracker/`

**Capability:** contract:security-tracker

**Kind:** interface

**Vendor:** agnostic

The seam between the `security-*` skills and the place a project keeps its security reports.
`contract:tracker` covers issue trackers in general;
this contract adds what handling embargoed reports needs on top of it —
named body fields, the single status rollup, attachments for the CVE record,
a confidentiality guard that refuses to write to a tracker that is not access-restricted,
and an explicit publish step for backends that write to a working copy.

See [`contract.md`](contract.md) for the operations, outputs, exit codes and backend rules.

| `tracker.platform` | Backend |
|---|---|
| `github` (default) | Private GitHub repository — [`tools/github/`](../github/operations.md), unchanged |
| `local-files` | Markdown files in a private Git or SVN working copy — [`tools/local-tracker/`](../local-tracker/README.md) |
| `jira` | Jira project with an issue-security level — [`tools/jira/`](../jira/README.md) |

ASF projects can also compare their tracker with the ASF Security team's dashboard,
or work from it when they keep no tracker of their own:
[`tools/asf-security-dash/`](../asf-security-dash/README.md).
It is read-only and not a `tracker.platform` value.

## Prerequisites

- **Runtime:** None — this directory is a Markdown contract spec; no executable code ships here.
- **CLIs / credentials / network:** Provided by the backend `tracker.platform` selects; see each backend's README.

## Configuration

In `<project-config>/project.md`, under the `tracker:` block:

```yaml
tracker:
  platform: local-files          # github (default) | local-files | jira
  local:
    root: security/reports       # tracker folder, relative to the tracker working copy
    checkout: ""                 # working copy path; empty = the repository the skill runs in
  jira:
    url: https://issues.example.org/jira
    project: FOOSEC
    security_level: "Security Team"
    issue_type: Bug
    deployment: server           # server | cloud
```

`/magpie-setup config` asks for the platform when it configures the security family,
and for `local-files` runs `detect` against the folder to learn the existing format before writing anything.
