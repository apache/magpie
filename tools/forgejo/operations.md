<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Forgejo / Gitea — CLI and API operation catalogue](#forgejo--gitea--cli-and-api-operation-catalogue)
  - [Authentication](#authentication)
  - [Running the REST recipes under the secure setup](#running-the-rest-recipes-under-the-secure-setup)
  - [Collaborator lookup (security-team roster)](#collaborator-lookup-security-team-roster)
  - [Issues](#issues)
    - [Read](#read)
    - [Create](#create)
    - [Edit — labels](#edit--labels)
    - [Edit — assignees](#edit--assignees)
    - [Edit — body](#edit--body)
    - [Comment](#comment)
    - [Close / reopen](#close--reopen)
  - [Milestones](#milestones)
    - [List](#list)
    - [Create](#create-1)
    - [Assign to an issue](#assign-to-an-issue)
  - [Labels](#labels)
    - [List](#list-1)
    - [Create](#create-2)
  - [Pull requests](#pull-requests)
    - [Create (public PR on the upstream repo)](#create-public-pr-on-the-upstream-repo)
    - [Edit — backport / other labels](#edit--backport--other-labels)
    - [Cross-link from the public PR back to the private tracker](#cross-link-from-the-public-pr-back-to-the-private-tracker)
  - [Projects](#projects)
  - [Error handling](#error-handling)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Forgejo / Gitea — CLI and API operation catalogue

Shared reference for the `tea` CLI (official Gitea/Forgejo CLI) and REST API invocations the skills use against the project's tracker repository. The skills reference this file for the recipe shape; each inline command in a skill already substitutes the tracker repo slug from the adopting project's manifest (see [`../../<project-config>/project.md`](../../<project-config>/project.md#repositories)).

Placeholder convention used below:

- `<tracker>` — the tracker repository slug from `<project manifest>.tracker_repo`.
- `<upstream>` — the upstream codebase slug from `<project manifest>.upstream_repo`.
- `<N>` — issue or PR number.
- `$FORGEJO_HOST` / `$TEA_TOKEN` — environment variables for REST API fallbacks.

## Authentication

Every skill's Step 0 pre-flight must verify that `tea` is authenticated:

```bash
tea --version                           # must show installed version
tea login list                          # must show logged-in user / server
```

A non-zero exit on either command is a hard stop — the skill reports the failure and asks the user to `tea login add` rather than retrying.
Subshell fetching like `$(gh auth token)` is avoided to comply with environment restrictions.
Note that `tea` CLI credentials come from `tea login add` (or `GITEA_SERVER_URL` / `GITEA_SERVER_TOKEN`); `$TEA_TOKEN` and `$FORGEJO_HOST` are environment variables required specifically for the REST API fallback recipes below.

## Running the REST recipes under the secure setup

The `curl` recipes in this file conflict with the framework's [secure agent setup](../../docs/setup/secure-agent-setup.md#the-frameworks-own-claudesettingsjson):
the settings it ships (the framework's own `.claude/settings.json`, which adopters copy) deny `Bash(curl *)` and `Bash(wget *)`,
because a network call made from Bash does not go through the sandbox's proxy.
Under that setup the agent can run the `tea` recipes, but not the REST-only ones
(collaborator lookup, comment read, issue create, body edit, comment, PR create, and the [status-rollup](status-rollup.md) and [issue-template](issue-template.md) body writes).

Until this adapter ships its own CLI — as [`tools/bitbucket/`](../bitbucket/README.md) and [`tools/discourse/`](../discourse/README.md) do, over the standard library's HTTP client, which honours the proxy variables —
a REST-only operation runs like this:

1. The agent writes the payload file with the Write tool, exactly as the recipe says.
2. The agent shows the user the exact `curl` command and the payload, and the user runs it **in their own terminal**, outside the agent session.
3. The user pastes the response back; the agent continues from it.

The vetted-ops `http-read` backend is not a route here: its catalogue is closed, read-only, and has no Forgejo operation (adding one is a reviewed change to [`ops.py`](../vetted-ops/src/vetted_ops/ops.py)).
Do not add a `curl` allow rule to make the recipes run: it would re-open Bash network egress for every command, not only these.

## Collaborator lookup (security-team roster)

Using the REST API fallback (since `tea` lacks a direct collaborators listing command), iterating pages until empty to ensure full roster retrieval without truncation:

```bash
page=1
while :; do
  curl -fsS -H "Authorization: token $TEA_TOKEN" \
    "$FORGEJO_HOST/api/v1/repos/<tracker>/collaborators?limit=50&page=$page" > <scratch>/collabs.json || exit 1
  jq -e 'type == "array"' <scratch>/collabs.json >/dev/null || exit 1
  if jq -e '. == []' <scratch>/collabs.json >/dev/null; then
    break
  fi
  jq -r '.[].login' <scratch>/collabs.json
  page=$((page + 1))
done
```

The authoritative "who is on the security team" list. Every collaborator counts regardless of permission level. Roster snapshots maintained in the project manifest files are caches of this command's output and can drift between changes.

## Issues

### Read

```bash
tea issues <N> --repo <tracker> --output json
```

When reading issue comments, you can use the REST API:
```bash
curl -fsS -H "Authorization: token $TEA_TOKEN" \
  "$FORGEJO_HOST/api/v1/repos/<tracker>/issues/<N>/comments" | jq .
```

### Create

A tracker title almost always derives from attacker-controlled text, so it **must not** be inlined into a shell argument or spliced with subshell commands. Use the Write tool (not Bash) to construct a JSON payload containing the title, body, and labels, then submit via the REST API:

*Write tool call:* `file_path: <scratch>/issue-payload.json`, `content: {"title": "<title>", "body": "<body>", "labels": [<label-ids>]}`

Title and body derive from reporter text: format `<scratch>/issue-payload.json` using the Write tool ensuring properly escaped JSON for any quotes, backslashes, or newlines. The `labels` array takes integer label IDs (retrieved from `tea labels ls --output json` or `GET /api/v1/repos/<tracker>/labels`), not string label names.

```bash
curl -fsS -X POST -H "Authorization: token $TEA_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @<scratch>/issue-payload.json \
  "$FORGEJO_HOST/api/v1/repos/<tracker>/issues" | jq .
```

### Edit — labels

```bash
tea issues edit <N> --repo <tracker> \
  --add-labels '<label-a>,<label-b>' \
  --remove-labels '<label-c>'
```

Apply every add + remove in **one** call so the change lands as a single audit-trail entry.

### Edit — assignees

```bash
tea issues edit <N> --repo <tracker> --add-assignees <handle>
```

### Edit — body

Because `tea issues edit` does not support a `--description-file` flag (only inline `-d, --description string`, which violates the rule against passing bodies as quoted arguments), issue body edits use the REST API PATCH endpoint.
Write the edited body to `<scratch>/issue-body.json` as a JSON payload using the Write tool:

*Write tool call:* `file_path: <scratch>/issue-body.json`, `content: {"body": "<edited body>"}` — the body is multi-line text, so write properly escaped JSON (quotes, backslashes and newlines escaped).

Then apply the update:

```bash
curl -fsS -X PATCH -H "Authorization: token $TEA_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @<scratch>/issue-body.json \
  "$FORGEJO_HOST/api/v1/repos/<tracker>/issues/<N>" | jq .
```

### Comment

```bash
curl -fsS -X POST -H "Authorization: token $TEA_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @<body-json-file> \
  "$FORGEJO_HOST/api/v1/repos/<tracker>/issues/<N>/comments"
```
(Format the `<body-json-file>` using Write tool to ensure properly escaped JSON `{"body": "..."}`)

Before posting, **scrub the comment body for bare-name mentions** of project maintainers and replace with `@`-handles.

### Close / reopen

```bash
tea issues close <N> --repo <tracker>
tea issues reopen <N> --repo <tracker>
```

## Milestones

### List

```bash
tea milestones ls --repo <tracker> --output json
```

### Create

```bash
tea milestones create --repo <tracker> \
  --title '<target>' \
  --description '<optional one-line description>'
```

### Assign to an issue

```bash
tea issues edit <N> --repo <tracker> --milestone '<title>'
```

## Labels

### List

```bash
tea labels ls --repo <tracker> --output json
```

### Create

```bash
tea labels create --repo <tracker> \
  --name '<name>' \
  --description '<short description>' \
  --color '<hex>'
```

Do **not** silently create labels without asking the user.

## Pull requests

### Create (public PR on the upstream repo)

Opening a public PR is irreversible. In GitHub workflows, `--web` is load-bearing so a human reviews scrubbed titles and Gen-AI disclosures in-browser before publishing. Since `tea pulls create` publishes immediately without an interactive browser check and lacks a `--description-file` flag (accepting only inline `-d, --description string`), the calling skill must:
1. Emit the interactive browser compare URL for human creation:
   `$FORGEJO_HOST/<upstream>/compare/<base-branch>...<user>:<branch>`
2. Or, if creating via API, display the scrubbed title, body, and Gen-AI disclosure to the user and obtain explicit interactive confirmation before executing:

*Write tool call:* `file_path: <scratch>/pr-payload.json`, `content: {"title": "<scrubbed title>", "body": "<body>", "head": "<user>:<branch>", "base": "<base-branch>"}` — write properly escaped JSON (quotes, backslashes and newlines escaped).

```bash
curl -fsS -X POST -H "Authorization: token $TEA_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @<scratch>/pr-payload.json \
  "$FORGEJO_HOST/api/v1/repos/<upstream>/pulls" | jq .
```

### Edit — backport / other labels

```bash
tea pr edit <N> --repo <upstream> --add-labels '<backport-label>'
```

### Cross-link from the public PR back to the private tracker

**Forbidden.** The public PR body and any follow-up public comment must not reveal the CVE, the security nature, or the private tracker URL. Enforce via the scrub step before writing the PR body.

## Projects

See [`project-board.md`](project-board.md) — Forgejo/Gitea project boards lack REST API card/column endpoints, so board reconciliation is a no-op across skills.

## Error handling

If any state-changing command fails, **stop the apply loop**, report the failure verbatim, and ask the user how to proceed — do not guess.
