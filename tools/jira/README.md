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
  - [Configuration](#configuration)
  - [Output contract](#output-contract)
  - [Write-path discipline](#write-path-discipline)
  - [Testing](#testing)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# JIRA bridge

**Capability:** contract:tracker

**Kind:** implementation

**Vendor:** Atlassian

JIRA REST helpers for the `issue-*` skill family.
Adopters with JIRA-based issue trackers wire this in as their
tracker bridge; adopters using GitHub Issues or other trackers
contribute a parallel `tools/<tracker>/` directory.

The bridge provides both **read** and **write** subcommands.
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
├── src/jira_bridge/   (package stub for test harness)
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

## Configuration

The bridge reads its configuration from the environment:

| Variable | Notes |
|---|---|
| `ISSUE_TRACKER_URL` | required; e.g. `https://issues.apache.org/jira` |
| `ISSUE_TRACKER_PROJECT` | project key (e.g. `FOO`) |
| `JIRA_API_TOKEN` | required for write subcommands — see auth notes below |
| `JIRA_AUTH_SCHEME` | `Basic` (default) or `Bearer` — see auth notes below |

The caller is responsible for exporting these (a skill resolves them
from [`<project-config>/issue-tracker-config.md`](../../projects/_template/issue-tracker-config.md)
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
- [`<project-config>/issue-tracker-config.md`](../../projects/_template/issue-tracker-config.md) —
  the adopter's tracker URL + project key.
