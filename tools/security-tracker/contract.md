<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Security tracker — backend contract](#security-tracker--backend-contract)
  - [Backends](#backends)
  - [From skill commands to vetted operations](#from-skill-commands-to-vetted-operations)
  - [Identifiers](#identifiers)
  - [Operations](#operations)
  - [Confidentiality guard — every backend refuses a public tracker](#confidentiality-guard--every-backend-refuses-a-public-tracker)
  - [Publishing local changes](#publishing-local-changes)
  - [What this contract does not cover](#what-this-contract-does-not-cover)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security tracker — backend contract

The operations every `security-*` skill performs on `<tracker>`, stated once,
independent of where the tracker lives.
A backend is selected per project by `tracker.platform` in
`<project-config>/project.md`, mirrored as `[tracker] platform` in the
[vetted-ops](../vetted-ops/README.md#tracker-backends) policy.
Skills never call a backend directly: every tracker command a skill writes as `gh`
is a [vetted operation](#from-skill-commands-to-vetted-operations), and vetted-ops
runs it against whichever backend the policy names.
Operations on `<upstream>` (public PRs, code search) are **not** part of this
contract — they stay on the project's forge.

## Backends

| `tracker.platform` | Backend | What a vetted operation runs |
|---|---|---|
| `github` (default) | Private GitHub repository | Its `gh` builder, per [`tools/github/operations.md`](../github/operations.md). Nothing changes for an existing adopter. |
| `local-files` | Markdown files in a folder of a private Git or SVN working copy | `magpie-local-tracker` — [`tools/local-tracker/`](../local-tracker/README.md) |
| `jira` | A Jira project whose issues carry an issue-security level | `magpie-jira-tracker` — [`tools/jira/`](../jira/README.md) |

The two non-GitHub backends expose **the same subcommand surface and the same
JSON output**, defined [below](#operations).
The vetted-ops policy pins the target (the tracker folder, or the Jira URL,
project and security level); the backend's code runs from the tool installed
beside vetted-ops, never from a path a policy names. A skill can name neither.

## From skill commands to vetted operations

The mapping that makes the skills backend-neutral, keyed by vetted operation.
The first column is the `gh` shape the security skills are written in; the skill
runs the vetted operation in the second column instead
(`vetted-op-read` for reads, `vetted-op-tracker` for the procedures and
`tracker-publish`, `vetted-op` for the other writes — the
[entry points](../vetted-ops/README.md#the-boundary-is-the-entry-point-not---caller)
keep their meaning on every backend).
The last two columns are what vetted-ops runs on a non-GitHub tracker.

| Skill command (`gh`) | Vetted operation | `local-files` / `jira` subcommand |
|---|---|---|
| `gh issue view <N> --repo <tracker> --json …` | `issue-view N` | `view N` |
| `gh issue view <N> --json comments`, `gh api …/issues/<N>/comments` | `issue-comments N` | `view N --comments` |
| `gh issue list --repo <tracker> --state S` | `issue-list S` | `list --state S` |
| `gh issue list --repo <tracker> --state S --label L` | `issue-list-label S L` | `list --state S --label L` |
| `gh search issues "<words>" --repo <tracker>`, `gh issue list --search …` | `issue-search "<words>"` (no `:` qualifiers) | `list --state all --search "<words>"` |
| `gh label list --repo <tracker>` | `label-list` | `labels` |
| `gh api repos/<tracker>/issues -F title=@… -F body=@…` | `issue-create "<title>" <body>` | `create --title "<title>" --body-file -` |
| `gh issue edit <N> --add-label L` | `issue-add-label N L` | `edit N --add-label L` |
| `gh issue edit <N> --remove-label L` | `issue-remove-label N L` | `edit N --remove-label L` |
| `gh issue edit <N> --milestone M` | `issue-set-milestone N M` | `edit N --milestone M` |
| `gh issue edit <N> --add-assignee U` | `issue-add-assignee N U` | `edit N --add-assignee U` |
| `gh issue edit <N> --remove-assignee U` | `issue-remove-assignee N U` | `edit N --remove-assignee U` |
| `gh issue edit <N> --body-file F` | `issue-edit-body N F` | `edit N --body-file -` |
| `gh issue edit <N> --title T` | `issue-edit-title N "<title>"` | `edit N --title "<title>"` |
| `gh issue comment <N> --body-file F` | `issue-comment N F` | `comment N --body-file -` |
| `gh issue close <N> --reason R` | `issue-close N R` | `close N --reason completed\|not-planned` |
| `gh issue reopen <N>` | `issue-reopen N` | `reopen N` |
| `vetted-op-tracker rollup-append` | `rollup-append N A F` | `rollup-append N --action A --entry-body-file -` |
| `vetted-op-tracker rollup-amend-latest` | `rollup-amend-latest N A F` | `rollup-amend-latest N --action A --entry-body-file -` |
| `vetted-op-read body-field-get` | `body-field-get N FIELD` | `field-get N FIELD` |
| `vetted-op-tracker body-field-set` | `body-field-set N FIELD F` | `field-set N FIELD --value-file -` |
| `gh api repos/<tracker> --jq .name` (Step 0 access check) | `tracker-doctor` | `doctor` |
| `generate-cve-json <N> --attach` (reads the issue) | `issue-body N` (saved), then `generate-cve-json --stdin` | `body N` (markdown `###` sections; Jira `h3.` converted) |
| `generate-cve-json <N> --attach` (attaches the JSON) | `issue-attach N FILE NAME` | `attach N - --name=NAME` |
| — (end of a session) | `tracker-pending` | `pending` (`local-files` only) |
| — (end of a session) | `tracker-publish F` | `publish --message-file - --push` (`local-files` only) |

Bodies always travel on stdin, from a file inside the vetted-ops workspace;
labels, milestones, assignees and close reasons must be values the policy declares.
These tracker operations have no counterpart and are **refused by name** on
`local-files` and `jira`, never approximated:
`milestone-list`, `milestone-create`, `milestone-close` (milestones are free values, listed in the policy),
`collaborators` (the roster comes from `release-trains.md`),
`comment-update` and `rollup-fold` (the rollup is kept by `rollup-append`; there are no legacy bot comments),
and the `board-*` operations (no project board).
`gh label create` needs no counterpart: labels are free strings on both backends.

## Identifiers

A tracker is addressed by an **ID string**: the issue number on GitHub
(`123`), the issue key on Jira (`FOOSEC-12`), the file or folder name in a
local tracker (`SEC-0012`).
Every backend also accepts the bare number and expands it with its own prefix.
Skills render an ID as a link with the `url` the backend returns; a local
tracker without `tracker.local.url_template` returns a repository-relative
path, which is a link inside the tracker and the bare ID everywhere else.

## Operations

Every output is one JSON document on stdout.
Errors go to stderr with a non-zero exit code.

These are the backend CLIs' subcommands — what the vetted operations above run.

| Operation | Arguments | Output | Reached from |
|---|---|---|---|
| `view <id>` | `--comments` | `{id, title, state, labels, assignees, milestone, author, created, updated, body, url, comments?}`; with `--comments` the status rollup is the first comment (`kind: "rollup"`), as on GitHub | `issue-view`, `issue-comments` |
| `list` | `--state open\|closed\|all` (default `open`), `--label L` (repeatable, AND), `--search TEXT`, `--limit N` | `[{id, title, state, labels, updated, url}]` | `issue-list`, `issue-list-label`, `issue-search` |
| `labels` | — | `["<label>", …]` (labels in use) | `label-list` |
| `field-get <id> <heading>` | — | `{id, heading, value}` (`value` is `null` when the section is missing) | `body-field-get` |
| `create` | `--title T` or `--title-file F`, `--body-file F`, `--label L` (repeatable) | `{id, url}` | `issue-create` |
| `edit <id>` | `--add-label`, `--remove-label`, `--add-assignee`, `--remove-assignee` (all repeatable), `--milestone M`, `--clear-milestone`, `--title T` or `--title-file F`, `--body-file F` | `{id, url}` | `issue-add-label` … `issue-edit-title` |
| `field-set <id> <heading>` | `--value-file F` | `{id, heading, created: bool}` | `body-field-set` |
| `comment <id>` | `--body-file F`, `--author A` | `{id, comment_id, url}` | `issue-comment` |
| `close <id>` | `--reason completed\|not-planned` | `{id, state}` | `issue-close` |
| `reopen <id>` | — | `{id, state}` | `issue-reopen` |
| `rollup-append <id>` | `--action A`, `--entry-body-file F`, `--user U`, `--now ISO8601` | `{id, url}` | `rollup-append` |
| `rollup-amend-latest <id>` | `--action A`, `--entry-body-file F` | `{id, url}`; exit 4 when the latest entry's action is not `A` | `rollup-amend-latest` |
| `attach <id> <file>` | `--name N` (required when `<file>` is `-`, stdin) | `{id, name, url}` | `issue-attach`, e.g. the patch of `security-issue-fix`'s Subversion flow |
| `body <id>` | — | the body as raw markdown with `###` field sections (not JSON), for `generate-cve-json --stdin` | `issue-body` |
| `pending` | — | `{backend, changes: [...], unpushed_commits, needs_publish: bool}` | `tracker-pending` |
| `publish` | `--message-file F`, `--trailer T` (repeatable), `--push` | `{committed, pushed, revision}` | `tracker-publish` |
| `doctor` | — | `{backend, ok, checks: [{name, ok, detail}]}` | direct, from `/magpie-setup config` |

Rules that hold for every backend:

- **Untrusted text never through a shell.** Bodies, comment and rollup text
  arrive through `--*-file` arguments (`-` for stdin), never as shell arguments —
  the same rule [`tools/github/operations.md`](../github/operations.md#create) sets
  for `gh`, for the same reason.
  `--title` exists for vetted-ops, which passes the validated one-line title as a
  single argv element with no shell; a human or skill typing a command uses
  `--title-file`.
- **Untrusted text never forges structure.** Every marker a backend parses back
  — comment markers and headings, the rollup marker, rollup entry summary lines,
  managed section headings — is escaped in incoming bodies before they are
  written, so a reporter's text cannot read back as another person's comment or
  rollup entry, or mislead `rollup-amend-latest`.
- **Labels and milestones are free strings.** The concrete names come from
  `tracker.labels` in `project.md`; a backend never invents a label.
- **Body fields are `###` sections by default.** `field-get` / `field-set`
  address the section whose heading matches `<heading>` case-insensitively;
  `field-set` creates the section at the end of the body when it is missing.
  A backend that stores fields differently (Jira wiki markup, a detected local
  format) maps the heading itself.
- **One rollup per tracker.** The rollup entries keep the shape of
  [`tools/github/status-rollup.md`](../github/status-rollup.md) — summary line
  `YYYY-MM-DD · @user · <Action>`, newest at the bottom — wherever the backend
  stores them.
- **Exit codes:** `0` success, `2` usage error, `3` tracker or section not
  found, `4` refused (a guard below, or an `amend-latest` mismatch), `5` backend
  error (I/O, HTTP, VCS).

## Confidentiality guard — every backend refuses a public tracker

The tracker holds embargoed vulnerability details.
A backend **must refuse to write** to a tracker it cannot show is access-restricted, and say why, with exit `4`:

- **`jira`** — every write checks that the issue carries exactly the
  configured issue-security level (a scheme can define levels open to every
  logged-in user, so "any level" is not enough), and `create` always sets
  `tracker.jira.security_level`.
  An issue without one is refused, never "fixed" by the backend.
- **`local-files`** — the backend refuses writes until the tracker's committed
  format descriptor records `access_restricted: true`, which only
  `detect --write --access-restricted` / `init --access-restricted` set.
  `/magpie-setup config` passes that flag only after the user confirms who can
  read the repository; it never decides that on its own.
  `doctor` reports the working copy's remotes and, for a GitHub remote, fails
  when the repository is public.
- **`github`** — unchanged: the tracker repository is private, per
  [`AGENTS.md`](../../AGENTS.md#confidentiality-of-the-tracker-repository).

## Publishing local changes

`github` and `jira` write to a server; each operation is visible to the team
when it returns.
`local-files` writes to a working copy, and nothing is shared until it is
committed and pushed.
So a skill that wrote through a `local-files` backend ends its run with a
**publish proposal**:

1. Run `vetted-op-read --caller <skill> tracker-pending` and show the changed files.
2. Draft a commit message naming the trackers touched and the action
   (`security: import SEC-0012, SEC-0013`), with the project's commit
   attribution resolved per
   [`docs/setup/commit-attribution.md`](../../docs/setup/commit-attribution.md).
3. Ask the user.
   On confirmation write the message, attribution trailer included as its last
   line, to a file in the vetted-ops workspace and run
   `vetted-op-tracker --caller <skill> tracker-publish <file>`
   (the backend's `publish --message-file - --push`).
   On Git that is `git add` + `git commit` of the tracker root only, then
   `git push`; on SVN it is `svn add` / `svn rm` for new and missing files and
   `svn commit`, which already publishes.
4. A push that needs credentials the sandbox withholds is a sandbox failure,
   not a lost key. `vetted-op-tracker` runs outside the sandbox for exactly this
   reason; if it is not wired that way, say so and point at
   [`docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md);
   never retry silently.

Never publish without the user's confirmation, and never publish files outside
the tracker root.

## What this contract does not cover

- **Project boards.** `local-files` and `jira` have no Projects V2 board;
  skills treat them as `tracker.project_board_enabled: false`.
- **Cross-links from public PRs.** The public PR on `<upstream>` may carry the
  tracker ID; whether it carries a URL depends on the backend having one.
- **Migration between backends.** Moving an existing GitHub tracker into files
  or Jira is out of scope.
