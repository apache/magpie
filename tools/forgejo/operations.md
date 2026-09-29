<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Forgejo / Gitea — CLI and API operation catalogue](#forgejo--gitea--cli-and-api-operation-catalogue)
  - [Authentication](#authentication)
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

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Forgejo / Gitea — CLI and API operation catalogue

Shared reference for the `tea` CLI (official Gitea/Forgejo CLI) and REST API invocations the skills use against the project's tracker repository. The skills reference this file for the recipe shape; each inline command in a skill already substitutes the tracker repo slug from the adopting project's manifest (see [`../../<project-config>/project.md`](../../<project-config>/project.md#repositories)).

Placeholder convention used below:

- `<tracker>` — the tracker repository slug from `<project manifest>.tracker_repo` (for Airflow, `<tracker>`).
- `<upstream>` — the upstream codebase slug from `<project manifest>.upstream_repo` (for Airflow, `<upstream>`).
- `<N>` — issue or PR number.
- `$FORGEJO_HOST` / `$TEA_TOKEN` — environment variables for REST API fallbacks.

## Authentication

Every skill's Step 0 pre-flight must verify that `tea` is authenticated:

```bash
tea --version                           # must show installed version
tea login list                          # must show logged-in user / server
```

A non-zero exit on either command is a hard stop — the skill reports the failure and asks the user to `tea login add` (or set `TEA_TOKEN`) rather than retrying. Subshell fetching like `$(gh auth token)` is avoided to comply with environment restrictions.

## Collaborator lookup (security-team roster)

Using the REST API fallback (since `tea` lacks a direct collaborators listing command):

```bash
curl -s -H "Authorization: token $TEA_TOKEN" \
  "$FORGEJO_HOST/api/v1/repos/<tracker>/collaborators" | jq -r '.[].login'
```

The authoritative "who is on the security team" list. Every collaborator counts regardless of permission level. Roster snapshots maintained in the project manifest files are caches of this command's output and can drift between changes.

## Issues

### Read

```bash
tea issues view <N> --repo <tracker> --output json
```

When reading issue comments, you can use the REST API:
```bash
curl -s -H "Authorization: token $TEA_TOKEN" \
  "$FORGEJO_HOST/api/v1/repos/<tracker>/issues/<N>/comments" | jq .
```

### Create

A tracker title almost always derives from attacker-controlled text, so it **must not** be inlined into a shell argument. Use the Write tool (not Bash) to put the title verbatim into a title file and the body into a body file, then pass both:

*Write tool call:* `file_path: <title-file>`, `content: <title>`

```bash
tea issues create --repo <tracker> \
  --title "$(cat <title-file>)" \
  --description-file <body-file> \
  --labels "<label-1>,<label-2>"
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
tea issues edit <N> --repo <tracker> --add-assignees @me
tea issues edit <N> --repo <tracker> --add-assignees <handle>
```

### Edit — body

```bash
tea issues edit <N> --repo <tracker> --description-file <tmpfile>
```

Write the edited body to a temp file first. The skills that perform "body-field surgery" read the full body, replace the targeted section, and write the result back via `--description-file`.

### Comment

```bash
curl -s -X POST -H "Authorization: token $TEA_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @<body-json-file> \
  "$FORGEJO_HOST/api/v1/repos/<tracker>/issues/<N>/comments"
```
(Format the `<body-json-file>` using Write tool to ensure properly escaped JSON `{"body": "..."}`)

Before posting, **scrub the comment body for bare-name mentions** of project maintainers and replace with `@`-handles.

### Close / reopen

```bash
tea issues edit <N> --repo <tracker> --state closed
tea issues edit <N> --repo <tracker> --state open
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

```bash
tea pr create --repo <upstream> \
  --base <base-branch> --head <user>:<branch> \
  --title "<neutral title>" \
  --description-file <path-to-body>
```

### Edit — backport / other labels

```bash
tea pr edit <N> --repo <upstream> --add-labels '<backport-label>'
```

### Cross-link from the public PR back to the private tracker

**Forbidden.** The public PR body and any follow-up public comment must not reveal the CVE, the security nature, or the private tracker URL. Enforce via the scrub step before writing the PR body.

## Projects

See [`project-board.md`](project-board.md) for the Forgejo REST API approach for Projects (as Forgejo does not use GraphQL Projects V2).

## Error handling

If any state-changing command fails, **stop the apply loop**, report the failure verbatim, and ask the user how to proceed — do not guess.
