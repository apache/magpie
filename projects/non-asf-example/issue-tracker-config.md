<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Velox Stream — issue-tracker configuration (non-ASF fixture)](#velox-stream--issue-tracker-configuration-non-asf-fixture)
  - [URL and project key](#url-and-project-key)
  - [Authentication](#authentication)
  - [Default query templates](#default-query-templates)
  - [Tracker-specific notes](#tracker-specific-notes)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Velox Stream — issue-tracker configuration (non-ASF fixture)

General-issue tracker for the fictional **Velox Stream** project, used
as a non-ASF adopter fixture. See [`README.md`](README.md) for context.

## URL and project key

| Key | Value |
|---|---|
| `url` | https://github.com/velox-community/velox-stream |
| `project_key` | velox-community/velox-stream |
| `tracker_type` | github-issues |
| `issue_url_template` | https://github.com/velox-community/velox-stream/issues/<N> |

Skills resolve `<issue-tracker>` to the `url` value above and
`<issue-tracker-project>` to `project_key`.

## Authentication

GitHub Issues authenticated via the `gh` CLI. The triager's token
must have `repo` read scope on `velox-community/velox-stream`.

| Key | Value |
|---|---|
| `anonymous_read` | true |
| `auth_method` | gh-cli |
| `auth_env_var` | (none — gh CLI credential store) |

## Default query templates

Stale-sweep and triage pools use GitHub Issues `gh` CLI syntax:

```text
# Triage pool — newly-filed issues awaiting initial label
is:open is:issue label:"needs triage" repo:velox-community/velox-stream

# Reassess pool — issues with no maintainer response in 60 days
is:open is:issue -label:"confirmed-bug" -label:"blocked" repo:velox-community/velox-stream
```

## Tracker-specific notes

- Rate limit: GitHub's API is 5 000 requests/hour authenticated;
  unauthenticated rate is 60/hour. The stale sweep typically issues
  < 50 API calls even for a large project.
- No custom JIRA fields — plain GitHub Issues only.
- No project board; column-transition steps in any skill are skipped
  (`project_board_enabled: false` in `project.md`).

## Cross-references

- [`project.md`](project.md) — core identity and security workflow config.
- [`stale-sweep-config.md`](stale-sweep-config.md) — thresholds for
  `issue-stale-sweep`.
