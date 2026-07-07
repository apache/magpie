<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [GitHub — CLI and API operation catalogue](#github--cli-and-api-operation-catalogue)
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
  - [GraphQL (Projects V2)](#graphql-projects-v2)
  - [Error handling](#error-handling)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# GitHub — CLI and API operation catalogue

Shared reference for the `gh` CLI and `gh api` / `gh api graphql`
invocations the skills use against the project's tracker repository.
The skills reference this file for the recipe shape; each inline
command in a skill already substitutes the tracker repo slug from the
adopting project's manifest (see
[`../../<project-config>/project.md`](../../<project-config>/project.md#repositories)).

Placeholder convention used below:

- `<tracker>` — the tracker repository slug from
  `<project manifest>.tracker_repo` (for Airflow, `<tracker>`).
- `<upstream>` — the upstream codebase slug from
  `<project manifest>.upstream_repo` (for Airflow, `<upstream>`).
- `<N>` — issue or PR number.

## Authentication

Every skill's Step 0 pre-flight must verify that `gh` is authenticated
and has collaborator access to `<tracker>`:

```bash
gh auth status                          # must show logged-in user + scopes
gh api repos/<tracker> --jq .name       # must return the repo name; 401/403/404 means stop
```

A non-zero exit on either command is a hard stop — the skill reports
the failure and asks the user to `gh auth login` (or to ask for
collaborator access to the tracker) rather than retrying.

## Collaborator lookup (security-team roster)

```bash
gh api repos/<tracker>/collaborators --jq '.[].login'
```

The authoritative "who is on the security team" list. Every
collaborator counts regardless of permission level (read / triage /
write / maintain / admin). Roster snapshots maintained in the project
manifest files (for Airflow, [`release-trains.md`](../../<project-config>/release-trains.md#security-team-roster))
are caches of this command's output and can drift between changes.

## Issues

### Read

```bash
gh issue view <N> --repo <tracker> \
  --json number,title,state,body,labels,milestone,assignees,author
```

Add `--json comments` when the skill needs the comment trail, and
`--json projectItems` when it needs to see which project boards the
issue sits on.

### Create

```bash
gh issue create --repo <tracker> \
  --title '<title>' \
  --body-file <path> \
  --label '<label-1>' --label '<label-2>'
```

Always write the body to a temp file and pass `--body-file` — shell
quoting silently corrupts anything with literal backticks, `$(…)`, or
newlines inside a multi-paragraph body.

### Edit — labels

```bash
gh issue edit <N> --repo <tracker> \
  --add-label '<label-a>,<label-b>' \
  --remove-label '<label-c>'
```

Apply every add + remove in **one** call so the change lands as a
single audit-trail entry rather than as N separate events.

### Edit — assignees

```bash
gh issue edit <N> --repo <tracker> --add-assignee @me         # self-assign
gh issue edit <N> --repo <tracker> --add-assignee <handle>    # named user
```

### Edit — body

```bash
gh issue edit <N> --repo <tracker> --body-file <tmpfile>
```

Write the edited body to a temp file first. The skills that perform
"body-field surgery" (updating one `### <field>` section without
touching the rest) read the full body, replace the targeted section
between its header and the next `### ` heading, and write the result
back via `--body-file`.

### Comment

```bash
gh issue comment <N> --repo <tracker> --body-file <tmpfile>
```

Before posting, **scrub the comment body for bare-name mentions** of
project maintainers / release managers / security-team members and
replace with `@`-handles. See the per-project mention rule (for
Airflow, [`../../<project-config>/naming-conventions.md#mentioning-airflow-maintainers-and-security-team-members`](../../<project-config>/naming-conventions.md#mentioning-airflow-maintainers-and-security-team-members))
for the grep-list of names to check.

### Close / reopen

```bash
gh issue close <N>  --repo <tracker> --reason completed   # or 'not planned'
gh issue reopen <N> --repo <tracker>
```

## Milestones

### List

```bash
gh api 'repos/<tracker>/milestones?state=all&per_page=100' \
  --jq '.[] | select(.title == "<target>") | {number, state}'
```

### Create

```bash
gh api repos/<tracker>/milestones \
  -f title='<target>' \
  -f state=open \
  -f description='<optional one-line description>'
```

The create call returns the milestone object including its `number` —
capture that in case the milestone is later closed (see fallback
below).

### Assign to an issue

```bash
gh issue edit <N> --repo <tracker> --milestone '<title>'
```

**Closed-milestone fallback.** `gh issue edit --milestone '<title>'`
fails with `'<title>' not found` if the milestone is closed. Fall back
to the REST API and reference it by number:

```bash
gh api repos/<tracker>/issues/<N> -X PATCH -F milestone=<number>
```

## Labels

### List

```bash
gh label list --repo <tracker> --limit 100 \
  --json name,description,color --jq '.[].name'
```

### Create

```bash
gh label create '<name>' --repo <tracker> \
  --description '<short description>' \
  --color '<hex>'
```

Do **not** silently create labels without asking the user. Label
names are the shared vocabulary of the security team, and new labels
should be discussed.

## Pull requests

### Create (public PR on the upstream repo)

```bash
gh pr create --web --repo <upstream> \
  --base <base-branch> --head <user>:<branch> \
  --title "<neutral title>" \
  --body "$(cat <path-to-body>)"
```

`--web` is load-bearing. Per the per-project convention (for Airflow,
see
[`../../<project-config>/fix-workflow.md#pr-creation-convention`](../../<project-config>/fix-workflow.md#pr-creation-convention)),
always open PRs through the browser so the human reviewer can check
the title, body, and Gen-AI disclosure before clicking **Create**.

### Edit — backport / other labels

```bash
gh pr edit <N> --repo <upstream> --add-label '<backport-label>'
```

Safe to run immediately after PR creation; the backport bot acts on
the label when the PR merges, not when it is applied.

### Cross-link from the public PR back to the private tracker

**Forbidden.** The public PR body and any follow-up public comment must
not reveal the CVE, the security nature, or the private tracker URL.
Enforce via the scrub step before writing the PR body — see the
per-project scrubbing rule (for Airflow,
[`../../<project-config>/fix-workflow.md#pr-title--body-scrubbing`](../../<project-config>/fix-workflow.md#pr-title--body-scrubbing)).

## GraphQL (Projects V2)

See [`project-board.md`](project-board.md) for the board
introspection and `updateProjectV2ItemFieldValue` patterns.

## Error handling

If any state-changing command fails, **stop the apply loop**, report
the failure verbatim, and ask the user how to proceed — do not guess.
Most sync-style skills order their apply list so the load-bearing edit
(usually the body edit) is first; a failure on a later step leaves the
body correct and a subsequent sync run will catch up the rest.
