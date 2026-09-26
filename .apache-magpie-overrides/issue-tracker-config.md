<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — issue-tracker configuration](#apache-magpie--issue-tracker-configuration)
  - [URL and project key](#url-and-project-key)
  - [Authentication](#authentication)
  - [Default query templates](#default-query-templates)
  - [Tracker-specific notes](#tracker-specific-notes)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — issue-tracker configuration

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
| `url` | `https://github.com/apache/magpie` |
| `project_key` | `apache/magpie` |
| `tracker_type` | `github-issues` |
| `issue_url_template` | `https://github.com/apache/magpie/issues/<N>` |

Skills resolve `<issue-tracker>` to `url` and `<issue-tracker-project>`
to `project_key`.

## Authentication

Apache Magpie's issues are public on GitHub: classification reads anonymously,
and every write (comment, label, close) goes through the maintainer's `gh`
CLI authentication.

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
| `anonymous_read` | `true` |
| `auth_method` | `gh-cli` |
| `auth_env_var` | — (gh CLI keychain auth) |

## Default query templates

The project uses GitHub Issues with the `family:*` / `capability:*`
taxonomy (docs/labels-and-capabilities.md). There is no `needs triage`
label: an issue with no labels at all is the untriaged pool.

```text
# triage pool — open issues nobody has labelled yet
is:open is:issue no:label repo:apache/magpie

# reassess pool — open issues silent for 90+ days
is:open is:issue repo:apache/magpie updated:<{today-90d}

# good-first-issue pool
is:open is:issue label:"good first issue" repo:apache/magpie
```

Adopters who use other trackers (Bugzilla, GitLab, custom) substitute
the appropriate query language.

## Tracker-specific notes

No project-specific quirks recorded yet; the generic notes below apply.

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
