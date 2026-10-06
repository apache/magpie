<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [JIRA bridge](#jira-bridge)
  - [Prerequisites](#prerequisites)
  - [Layout](#layout)
  - [Invocation](#invocation)
  - [Read subcommands](#read-subcommands)
    - [`search <JQL>`](#search-jql)
    - [`issue <KEY>`](#issue-key)
    - [`projects`](#projects)
  - [Write subcommands](#write-subcommands)
    - [`comment <KEY> --body-file <path>`](#comment-key---body-file-path)
    - [`transition <KEY> <transition-name>`](#transition-key-transition-name)
    - [`label <KEY> --add <name> --remove <name>`](#label-key---add-name---remove-name)
    - [`assign <KEY> <username>`](#assign-key-username)
    - [`field <KEY> <field-name> --value <value>` / `--value-json <json>`](#field-key-field-name---value-value----value-json-json)
    - [`attach <KEY> <file>`](#attach-key-file)
  - [People and contributor-activity reads](#people-and-contributor-activity-reads)
  - [Configuration](#configuration)
  - [Output contract](#output-contract)
  - [Write-path discipline](#write-path-discipline)
  - [Testing](#testing)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# JIRA bridge

**Capability:** contract:tracker + contract:people

**Kind:** implementation

**Vendor:** Atlassian

JIRA REST helpers for the `issue-*` skill family.
Adopters with JIRA-based issue trackers wire this in as their
tracker bridge; adopters using GitHub Issues or other trackers
contribute a parallel `tools/<tracker>/` directory.

The bridge provides both **read** and **write** subcommands.
The read-only contributor-activity queries of `contract:tracker` run in Python, in the `jira` backend of [`tools/contributor-metrics`](../contributor-metrics/README.md#backends), through this package's read-only REST client, `jira_bridge.rest`; the profile lookup of `contract:people` is a single REST read. See [People and contributor-activity reads](#people-and-contributor-activity-reads).
Write operations require `JIRA_API_TOKEN` and follow the same
write-path discipline as the GitHub bridge: every mutation is
gated on explicit user confirmation in the calling skill — the
bridge only executes confirmed actions.

## Prerequisites

- **Runtime:** Groovy 4.x+ on `PATH` (`groovy tools/jira/bridge.groovy …`); `@Grab` pulls the HTTP-client dependencies on first run, no separate install step. Python 3.11+ via `uv` is needed only for the pytest test harness.
- **CLIs:** `groovy` (4.x — the `@Grab` coordinate uses the `org.apache.groovy` group ID); `uv` only to run the tests.
- **Credentials / auth:** `ISSUE_TRACKER_URL` (required) and `ISSUE_TRACKER_PROJECT` exported by the caller; write subcommands require `JIRA_API_TOKEN` (`JIRA_AUTH_SCHEME` = `Basic` default, or `Bearer` for ASF PATs). Anonymous-read trackers need no auth for read subcommands.
- **Network:** the configured `<issue-tracker>` JIRA host (e.g. `issues.apache.org/jira`); `@Grab` reaches Maven Central on first run to resolve dependencies.
- **Optional:** `groovy` on `PATH` for the pytest suite — tests auto-skip when Groovy is absent.

## Layout

```text
tools/jira/
├── README.md          (this file)
├── bridge.groovy      (Groovy reference implementation)
├── pyproject.toml     (Python test harness config)
├── src/jira_bridge/   (read-only Python REST client, rest.py; test harness package)
└── tests/             (pytest test suite)
```

Other languages (Python, Bash + curl) are welcome via PR.

## Invocation

```bash
groovy tools/jira/bridge.groovy <subcommand> [args]
```

The Groovy implementation uses `@Grab` for HTTP client dependencies
— no separate install step. Requires Groovy 4.x or newer on
`PATH` (the `@Grab` coordinate uses `org.apache.groovy`, which
is the Groovy 4 group ID).

## Read subcommands

### `search <JQL>`

Run a JQL query against `<issue-tracker>` and emit matching issues
as JSON to stdout:

```bash
groovy tools/jira/bridge.groovy search \
  'project = <KEY> AND status = Open AND resolution = Unresolved'
```

Output (truncated):

```json
{
  "total": 42,
  "issues": [
    {"key": "<KEY>-9999", "title": "...", "status": "Open", "components": [...], "fixVersion": "..."},
    ...
  ]
}
```

The `--limit <N>` flag caps the result count (default: 50).

### `issue <KEY>`

Fetch a single issue's full state (body, comments, attachments
list, labels, fixVersion, etc.) as JSON:

```bash
groovy tools/jira/bridge.groovy issue <KEY>-9999
```

Output is the JIRA REST `/rest/api/2/issue/<KEY>` response,
shaped for skill consumption.

### `projects`

List the JIRA projects available at the configured
`<issue-tracker>` URL. Useful during initial adoption to confirm
the project key is correct.

```bash
groovy tools/jira/bridge.groovy projects
```

## Write subcommands

All write subcommands require `JIRA_API_TOKEN` to be set and
follow the write-path discipline described below.

### `comment <KEY> --body-file <path>`

Post a comment on an issue. The comment body is read from a file
to avoid shell-quoting issues:

```bash
groovy tools/jira/bridge.groovy comment FOO-9999 --body-file /tmp/comment.txt
```

Output:

```json
{"ok": true, "key": "FOO-9999", "commentId": "12345"}
```

### `transition <KEY> <transition-name>`

Move an issue to a new workflow state. The transition name is
resolved case-insensitively against the issue's available
transitions:

```bash
groovy tools/jira/bridge.groovy transition FOO-9999 "Resolve Issue"
```

Output:

```json
{"ok": true, "key": "FOO-9999", "transition": "Resolve Issue", "transitionId": "21"}
```

If the transition name does not match any available transition,
the command exits with an error listing the valid names.

### `label <KEY> --add <name> --remove <name>`

Toggle labels on an issue. Both `--add` and `--remove` can be
specified multiple times in a single call:

```bash
groovy tools/jira/bridge.groovy label FOO-9999 --add security --remove needs-triage
```

Output:

```json
{"ok": true, "key": "FOO-9999", "added": ["security"], "removed": ["needs-triage"]}
```

Uses JIRA's atomic `update` API — no read-modify-write race.

### `assign <KEY> <username>`

Set the assignee on an issue. Data Center only — Cloud uses
`accountId`, which is not currently supported:

```bash
groovy tools/jira/bridge.groovy assign FOO-9999 jdoe
```

Output:

```json
{"ok": true, "key": "FOO-9999", "assignee": "jdoe"}
```

### `field <KEY> <field-name> --value <value>` / `--value-json <json>`

Edit a single field (including custom fields) on an issue.
Use `--value` for plain string/number values. Use `--value-json`
for structured values (priority, version, single-select, user
picker, etc.):

```bash
# String value
groovy tools/jira/bridge.groovy field FOO-9999 customfield_10100 --value "high"

# Structured value (e.g. priority)
groovy tools/jira/bridge.groovy field FOO-9999 priority --value-json '{"name":"High"}'

# Array value (e.g. fixVersions)
groovy tools/jira/bridge.groovy field FOO-9999 fixVersions --value-json '[{"name":"1.2.3"}]'
```

Output:

```json
{"ok": true, "key": "FOO-9999", "field": "priority", "value": {"name": "High"}}
```

### `attach <KEY> <file>`

Attach a file to an issue:

```bash
groovy tools/jira/bridge.groovy attach FOO-9999 /tmp/report.txt
```

Output:

```json
{"ok": true, "key": "FOO-9999", "attachments": [{"id": "99", "filename": "report.txt"}]}
```

## People and contributor-activity reads

The read-only activity queries of [`contract:tracker`](../tracker/README.md) and the profile lookup of [`contract:people`](../people/README.md), against the same Jira Data Center REST API v2 the bridge uses and with the same configuration (`ISSUE_TRACKER_URL`, `ISSUE_TRACKER_PROJECT`, `JIRA_API_TOKEN`, `JIRA_AUTH_SCHEME`).
The per-person streams are implemented by the `jira` backend of [`tools/contributor-metrics`](../contributor-metrics/README.md#backends) over `jira_bridge.rest`; the others are plain REST reads a skill makes.

`jira_bridge.rest` treats the token as the user's personal credential and the URL as project configuration, which anyone with write access can commit:

- the URL must be `https://` (`http://` only for `localhost`, `127.0.0.1` or `::1`);
- the token is sent only to the host the user confirmed for it — `JIRA_API_HOST`, or a `host=` line beside a `token=` line in `~/.config/apache-magpie/jira-token` — and only on requests to that host; for any other host it is withheld, reads go out anonymously, and the caller is told why;
- redirects are refused, so the token never follows one;
- the token never appears in an error message.
`<user>` is the person's Jira username, validated against `[A-Za-z0-9._@+-]{1,255}` before it reaches a query.

| Verb | Jira resolution |
|---|---|
| tracker `list_filed(<user>, since, end)` | `GET /rest/api/2/search` with JQL `project = "<KEY>" AND reporter = "<user>" AND created >= "<since>" AND created <= "<end> 23:59"` |
| tracker `list_triaged(<user>, since, end)` | `GET /rest/api/2/search?expand=changelog&fields=comment,…` over `project = "<KEY>" AND updated >= "<since>" AND created <= "<end> 23:59"`; an issue the user did not report counts when its changelog shows the user changing `status`, `labels`, `component`, `priority`, `assignee`, `resolution` or `Fix Version`, or the user commented, inside the window — dated by the first such action |
| tracker `list_commented(<user>, since, end)` | the same search; an issue counts when the user commented inside the window, dated by the first such comment |
| tracker `list_created(since, until)` | `project = "<KEY>" AND created >= "<since>" AND created <= "<until> 23:59"`; `author_first_time` from one `reporter = "<author>" AND created < "<created>"` count per author |
| tracker `first_reply(<KEY-N>)` | `GET /rest/api/2/issue/<KEY-N>/comment`, the first comment by a rostered maintainer (Jira has no author-association signal) |
| people `get_profile(<user>)` | `GET /rest/api/2/user?username=<user>` → `displayName`; a 404 means the account does not exist. Organisation, website and linked accounts are not exposed: `null`. |
| people `list_collaborators`, `add_team_member` | not provided — Jira has no repository collaborators or forge teams (`NotApplicable`) |

Jira has no pull requests: authored changes and reviews come from the project's code host through `contract:change-request`.
Comment bodies are read inside the backend to find pushback candidates and never leave it.

## Configuration

The bridge reads its configuration from the environment:

| Variable | Notes |
|---|---|
| `ISSUE_TRACKER_URL` | required; e.g. `https://issues.apache.org/jira` |
| `ISSUE_TRACKER_PROJECT` | project key (e.g. `FOO`) |
| `JIRA_API_TOKEN` | required for write subcommands — see auth notes below |
| `JIRA_AUTH_SCHEME` | `Basic` (default) or `Bearer` — see auth notes below |

The caller is responsible for exporting these (a skill resolves them
from [`<project-config>/issue-tracker-config.md`](../../plugins/magpie-setup/templates/issue-tracker-config.md)
and passes them in the environment). Direct file-fallback inside the
bridge is a possible future enhancement — it is **not** implemented
today; the bridge exits if `ISSUE_TRACKER_URL` is unset.

For anonymous-read trackers, no auth is required for read
subcommands. Write subcommands always require `JIRA_API_TOKEN` and
exit with an error if it is unset.

**Authentication:** This bridge targets JIRA Data Center (DC),
specifically ASF JIRA at `issues.apache.org/jira`. Cloud is not
currently supported (`assign` uses DC `name`, not Cloud
`accountId`).

- **Basic auth (default):** set `JIRA_API_TOKEN` to the
  base64-encoded `username:password` or `username:pat` string.
- **Bearer auth (ASF PATs):** set `JIRA_AUTH_SCHEME=Bearer` and
  `JIRA_API_TOKEN` to the raw PAT string. ASF JIRA DC PATs use
  `Authorization: Bearer <pat>`.

## Output contract

Every subcommand emits JSON to stdout on success, or a non-zero
exit code with a human-readable error to stderr on failure.

Write subcommands return `{"ok": true, "key": "<KEY>", ...}` with
operation-specific fields as documented per subcommand above.

The output schema is documented per subcommand above. Skills
parse the JSON via standard JSON tooling — no special envelope,
no wrapper.

## Write-path discipline

The bridge executes mutations but does **not** decide whether to
mutate. Every write operation is gated on **explicit user
confirmation** in the calling skill — the bridge only executes
confirmed actions.

This mirrors the GitHub bridge's write-path discipline (see
[`tools/github/operations.md`](../github/operations.md)): skills
surface the proposed action to the maintainer, wait for
confirmation, then call the bridge to execute.

## Testing

The test suite uses a mock HTTP server and requires `groovy` on
`PATH`. Tests are skipped automatically when Groovy is not
available.

```bash
cd tools/jira
uv run pytest
```

## Cross-references

- [`issue-triage`](../../skills/issue-triage/SKILL.md) —
  primary consumer (selector resolution + per-issue fetch).
- [`issue-reassess`](../../skills/issue-reassess/SKILL.md) —
  campaign-level consumer (pool fetch).
- [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) —
  write-path consumer (label, transition, comment, field updates).
- [`security-issue-invalidate`](../../skills/security-issue-invalidate/SKILL.md) —
  write-path consumer (close with label + comment).
- [`tools/github/operations.md`](../github/operations.md) —
  write-path discipline reference.
- [`<project-config>/issue-tracker-config.md`](../../plugins/magpie-setup/templates/issue-tracker-config.md) —
  the adopter's tracker URL + project key.
