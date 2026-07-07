<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — issue-tracker configuration](#todo-project-name--issue-tracker-configuration)
  - [URL and project key](#url-and-project-key)
  - [Authentication](#authentication)
  - [Default query templates](#default-query-templates)
  - [Tracker-specific notes](#tracker-specific-notes)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — issue-tracker configuration

The project's **general-issue tracker** configuration — where issues
live, how to authenticate, and how to query. Consumed by the
`issue-*` skill family (`issue-triage`, `issue-reassess`,
`issue-reproducer`, `issue-fix-workflow`).

This file is distinct from the `tracker_repo` field in
[`project.md`](project.md), which declares the **security** tracker
used by the `security-issue-*` skill family. Many projects use
different trackers for the two: e.g., a private GitHub repo for
security and a public JIRA project for general issues. Adopters
that use the same tracker for both can point both at the same
location.

## URL and project key

| Key | Value |
|---|---|
| `url` | TODO: tracker base URL. JIRA example: `https://issues.apache.org/jira`. GitHub Issues example: `https://github.com/<owner>/<repo>` |
| `project_key` | TODO: project identifier within the tracker. JIRA example: `FOO` (one-word uppercase). GitHub Issues example: `owner/repo`. |
| `tracker_type` | TODO: one of `jira`, `github-issues`, `bugzilla`, `gitlab-issues`, or `custom`. |
| `issue_url_template` | TODO: URL pattern for an individual issue. JIRA example: `https://issues.apache.org/jira/browse/<KEY>`. GitHub Issues example: `https://github.com/<owner>/<repo>/issues/<N>`. |

Skills resolve `<issue-tracker>` to `url` and `<issue-tracker-project>`
to `project_key`.

## Authentication

TODO: describe how the skills should authenticate.

- **Anonymous read** — true if the tracker permits unauthenticated
  browsing (many JIRA instances do). Set `anonymous_read: true` if
  so; skills can do the classification phase without credentials.
- **Authenticated write** — credentials needed to post comments,
  link issues, or apply any mutation. Document where credentials
  come from:
  - JIRA: API token in `~/.config/<tracker>-token` or an env var
  - GitHub Issues: `gh` CLI auth status
  - Other: project-specific

| Key | Value |
|---|---|
| `anonymous_read` | TODO: `true` or `false` |
| `auth_method` | TODO: e.g. `gh-cli`, `jira-api-token`, `pat` |
| `auth_env_var` | TODO: env-var name carrying the token, if applicable |

## Default query templates

TODO: the project's canonical queries for the triage / reassess
pools. Skills use these as defaults; users can override per-invocation.

For JIRA-based projects, queries are JQL:

```text
# TODO: triage pool — newly-filed, unsorted issues
project = <project_key> AND resolution = Unresolved AND status = Open

# TODO: reassess pool — silent wishlists and EOL issues
project = <project_key> AND resolution = Unresolved AND
  fixVersion in unreleasedVersions() AND status = Open

# TODO: reopened pool — issues that were closed and reopened
project = <project_key> AND status changed FROM "Closed" TO "Open"
```

For GitHub-Issues-based projects, queries are `gh search issues`
syntax:

```text
# TODO: triage pool
is:open is:issue label:"needs triage" repo:<owner>/<repo>

# TODO: reassess pool
is:open is:issue label:"good first issue" repo:<owner>/<repo>
```

Adopters who use other trackers (Bugzilla, GitLab, custom) substitute
the appropriate query language.

## Tracker-specific notes

TODO: capture quirks the skills should know about.

- **Rate limits** — most public trackers throttle. JIRA Cloud's free
  tier is 1500 requests / 5 minutes; GitHub's API is 5000 / hour
  authenticated.
- **Anon vs auth differences** — if anonymous queries return fewer
  fields than authenticated ones (e.g., JIRA's `worklog`), skills
  must know to escalate.
- **Custom fields** — JIRA projects often define custom fields
  (`customfield_NNNNN`). Document any the skills need to read.
- **Project board / kanban integration** — if the tracker has a
  separate "board" view with workflow states, document where it is
  and whether the skills should reconcile against it.

## Cross-references

- [`project.md`](project.md) — the manifest; declares
  `upstream_default_branch` and the security `tracker_repo` (distinct
  from this file's general-issue tracker).
- [`reassess-pool-defaults.md`](reassess-pool-defaults.md) — pool
  definitions consumed by `issue-reassess`, extending the default
  queries above.
- [`runtime-invocation.md`](runtime-invocation.md) — how `issue-reproducer`
  runs the extracted code.
