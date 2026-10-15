<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Jira security tracker](#jira-security-tracker)
  - [Prerequisites](#prerequisites)
  - [What it is](#what-it-is)
  - [Invocation](#invocation)
  - [Configuration](#configuration)
  - [Storage format](#storage-format)
  - [Confidentiality guard](#confidentiality-guard)
  - [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Jira security tracker

**Capability:** contract:security-tracker
**Kind:** implementation
**Vendor:** Atlassian

The `jira` backend of the [security-tracker contract](../security-tracker/contract.md).
It keeps a project's security trackers in a **private Jira project** whose issues carry an issue-security level, and exposes the same subcommand surface and JSON output as the [`local-files` backend](../local-tracker/README.md), so a skill swaps only the command prefix.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; standard library only, no third-party dependencies.
- **CLIs:** `uv`; nothing else.
- **Credentials / auth:** `JIRA_API_TOKEN`, with `JIRA_AUTH_SCHEME` (`Basic` default, `Bearer` for Data Center personal access tokens) and optionally `JIRA_USER`; see [Configuration](#configuration).
- **Network:** the Jira host named by `ISSUE_TRACKER_URL` (for example `issues.apache.org`), over HTTPS.

## What it is

A Jira project can serve as `<tracker>` when every issue in it is hidden behind an **issue-security level** that only the security team can see.
The level is what makes the tracker private: Jira projects are frequently browsable by any logged-in user, and an issue without a level is visible to everyone who can browse the project.
So the level is mandatory, not a convenience.
`create` always sets the configured level and refuses to run without one, and every write on an existing issue checks that the issue carries a level first (see [Confidentiality guard](#confidentiality-guard)).

The backend talks to Jira's REST API v2 (`/rest/api/2/…`), which Jira Server, Data Center and Cloud all accept.
Descriptions and comments are Jira **wiki markup** strings.
Every write is immediate, so `pending` always reports nothing to publish and `publish` is a no-op.

## Invocation

```bash
uv run --project <framework>/tools/jira-security-tracker magpie-jira-tracker <op> [args…]
```

The operations, their arguments, JSON output and exit codes are the ones in the [contract](../security-tracker/contract.md#operations).
Backend-specific details:

| Operation | Jira mapping |
|---|---|
| IDs | `FOOSEC-12`, or a bare `12` expanded with the project key; an ID from another project is a usage error. |
| `view` | `state` is `closed` when the issue has a resolution or its status category is *Done*; `milestone` is the first fix version; `assignees` holds the single assignee. Adds `security_level` and `warnings` (a warning when the issue has no level). |
| `list` | JQL `project = KEY` plus `resolution is EMPTY` / `is not EMPTY`, one `labels = "L"` per label, `text ~ "…"` for `--search`, ordered by `updated DESC`. |
| `labels` | Distinct labels across the project's issues (scans at most 5000 issues). |
| `create` | Sets `summary` (the title file collapsed to one line), `description`, `labels`, `issuetype` and `security`. |
| `edit` | Labels through `update.labels` add / remove operations, `fixVersions` for the milestone, `assignee` for the (single) assignee. |
| `comment` | `--author` is reported back but ignored: Jira records the authenticated user as the author. |
| `close` / `reopen` | Picks a transition whose target status category is *Done* (or not *Done* for `reopen`, preferring one named *Reopen*). `close` sets resolution `Fixed` (`completed`) or `Won't Fix` (`not-planned`), and retries without a resolution when the transition screen rejects it. |
| `attach` | Multipart upload to `/rest/api/2/issue/<key>/attachments`; `--name` is reduced to a base name. |
| `doctor` | Checks URL, project, token, configured level, `/myself`, project reachability, and that the level exists. A 403 or 404 on the level listing reports the level as *unverified*, not failed. Exits `0`; read `ok`. |

On Jira Cloud the deprecated `/rest/api/2/search` is replaced by `/rest/api/2/search/jql`, and assignees are account IDs; set `JIRA_DEPLOYMENT=cloud` (or pass `--jira-cloud`) for both.

## Configuration

Settings come from flags or the environment; a calling skill exports them from the `tracker.jira.*` keys in `<project-config>/project.md`.

| Flag | Environment | `project.md` key | Meaning |
|---|---|---|---|
| `--url` | `ISSUE_TRACKER_URL` | `tracker.jira.url` | Jira base URL, for example `https://issues.apache.org/jira`. |
| `--project` | `SECURITY_TRACKER_PROJECT` | `tracker.jira.project` | Key of the private project, for example `FOOSEC`. |
| `--security-level` | `SECURITY_TRACKER_SECURITY_LEVEL` | `tracker.jira.security_level` | Name of the issue-security level `create` sets. Required for `create`. |
| `--issue-type` | `SECURITY_TRACKER_ISSUE_TYPE` | `tracker.jira.issue_type` | Issue type for `create`; default `Bug`. |
| `--jira-cloud` | `JIRA_DEPLOYMENT=cloud` | `tracker.jira.deployment: server\|cloud` | Cloud search endpoint and account-ID assignees. Default `server`. |
| — | `JIRA_API_TOKEN` | — | API token or personal access token. |
| — | `JIRA_AUTH_SCHEME` | — | `Basic` (default) or `Bearer`. |
| — | `JIRA_USER` | — | With `Basic`, the user name to pair with a raw token. |

Authentication follows the [Groovy Jira bridge](../jira/README.md): with `Bearer` the token is sent as-is; with `Basic` a token that already is a base64 `user:secret` string is sent as-is, and a raw token is encoded together with `JIRA_USER`.
The project key is deliberately a separate variable from the bridge's `ISSUE_TRACKER_PROJECT`, which names the project's public issue tracker.
Keep the token outside the project tree, per the repository's rule on tool credentials.

## Storage format

**Body fields** are level-3 sections of the description, `h3. <Heading>`, running until the next `h1.`–`h3.` heading.
`field-get` and `field-set` match the heading case-insensitively, and `field-set` appends a new `h3.` section at the end when the heading is missing.
Markdown `### <Heading>` sections are read too, so a description pasted from a GitHub issue form still resolves; headings inside `{code}`, `{noformat}` and fenced blocks are ignored.

**The status rollup** is one comment per issue whose first line is the invisible wiki anchor `{anchor:magpie-status-rollup-v1}`.
Each entry is a bold summary line, a blank line and the entry body, and entries are separated by a `----` line, oldest first:

```text
{anchor:magpie-status-rollup-v1}
*2026-10-01 · @alice · Import*

Imported from the security@ thread.

----

*2026-10-02 · @bob · Sync*

Synced labels and fix version.
```

`rollup-append` creates the comment or rewrites it with the new entry at the bottom; `rollup-amend-latest` replaces only the latest entry's body, keeping its date and user, and exits `4` when the latest action differs from `--action`.
The default user is `--user`, else the authenticated user's `name` (or `displayName` on Cloud).
Neither command prints the rollup text; both output only `{id, url}`.

## Confidentiality guard

Before every write on an existing issue (`edit`, `field-set`, `comment`, `close`, `reopen`, `rollup-append`, `rollup-amend-latest`, `attach`) the backend reads the issue's `security` field.
When the issue has no issue-security level, it refuses with exit `4` and says the issue is not access-restricted, before sending any content.
It never sets the level on an existing issue itself: an issue without one may already have been exposed, and a human decides what to do about it.
`create` without a configured level is refused the same way.
Reads (`view`, `list`, `field-get`) still work, and `view` carries a warning for an unrestricted issue.

## Testing

```bash
uv run --project tools/jira-security-tracker --group dev pytest tools/jira-security-tracker/tests
```

The tests inject a fake transport into `JiraClient`, record every request, and never reach the network.
