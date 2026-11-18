<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [GitHub — project board (Projects V2)](#github--project-board-projects-v2)
  - [What the board is for](#what-the-board-is-for)
  - [Auto-add workflow filter](#auto-add-workflow-filter)
  - [Per-project configuration](#per-project-configuration)
  - [Create a board](#create-a-board)
  - [Keep the board security-only](#keep-the-board-security-only)
  - [Introspection — find the itemId and current column](#introspection--find-the-itemid-and-current-column)
  - [Introspection — re-fetch the option IDs](#introspection--re-fetch-the-option-ids)
  - [Write — move a tracker to a different column](#write--move-a-tracker-to-a-different-column)
  - [Orphan-issue path](#orphan-issue-path)
  - [Archive a board item — terminal-state cleanup](#archive-a-board-item--terminal-state-cleanup)
    - [Archive recipe](#archive-recipe)
    - [Idempotency](#idempotency)
    - [Inverse — unarchive](#inverse--unarchive)
  - [When the board is a no-op](#when-the-board-is-a-no-op)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# GitHub — project board (Projects V2)

The **project board** is the security team's primary overview surface:
a Projects V2 board where every tracking issue sits in exactly one
`Status` column representing its current lifecycle state. The
`security-issue-sync` skill reads the current column as part of its
state-gather, and reconciles it against the issue's labels + body
state as part of its apply loop.

Board-column mutations go through the GitHub GraphQL API
(`updateProjectV2ItemFieldValue`) — the `gh` CLI does not expose a
flag-based interface for Projects V2.

**Under the secure setup, use the vetted operations instead of the raw
recipes below:** `board-item <N>` reads the issue's node id and its board
item (id, column, archived), and `board-add-item`, `board-set-status` and
`board-archive-item` make the writes, each behind a prompt
([vetted-ops → The project board](../vetted-ops/README.md#the-project-board)).
The GraphQL below is what those operations run, and stays the reference for
a setup without vetted-ops.

## What the board is for

- Reads: humans scanning *"who is on what right now"*, agents
  verifying that the tracker's label-derived state matches the board
  column before proposing the next transition.
- Writes: sync-style skills moving the tracker from one column to
  the next whenever a label / body state change warrants it.

## Auto-add workflow filter

The board's built-in **"Auto-add to project"** workflow decides which
newly-opened issues land on the board automatically. The filter
**must gate on the `security issue` label** so that only security
trackers are added, not every issue opened in `tracker_repo`:

```text
is:issue label:"security issue"
```

This pairs with two upstream guarantees that ensure every legitimate
security tracker carries the label:

1. The repo's [issue template](issue-template.md) lists `security
   issue` in its `labels:` frontmatter, so any tracker created via
   *New issue → Airflow Security Issue* gets the label automatically.
2. The `security-issue-import` skill passes `--label 'security issue'`
   on every `gh issue create` it runs.

Manually-opened issues (no template, no skill) will not appear on the
board until a triager applies the label by hand — that is the
intended behaviour, since such issues are usually noise.

**This filter is UI-only.** GitHub's GraphQL API exposes the workflow's
`id` / `name` / `enabled` fields but **not** the filter expression, so
neither `gh` nor a GraphQL mutation can set it. To change it:

1. Open `<project_board_url>/workflows` (for Airflow:
   <<project-board-url>/workflows>).
2. Click **Auto-add to project**.
3. Edit the **Filter** field to the expression above.
4. Save.

If the workflow is ever disabled or its filter is widened, freshly-
created trackers will land in the *orphan-issue* path (see below) and
need an explicit `addProjectV2ItemById` call before any column
mutation can succeed.

## Per-project configuration

Three values are project-specific and live in the adopting project's
manifest:

1. **Project node ID** (`project_board_node_id`) — the opaque
   `PVT_*` ID that identifies the board. Fetch once; stable unless
   the board is deleted and recreated.
2. **Status field node ID** (`status_field_node_id`) — the opaque
   `PVTSSF_*` ID of the `Status` single-select field. Stable unless
   the field is deleted and recreated.
3. **Column → option-ID mapping** (`status_column_option_ids`) — each
   column of the `Status` field has an opaque `ProjectV2SingleSelectFieldOption`
   ID. **These regenerate whenever the column list is edited** —
   renaming a column, adding a new one, or re-ordering them all
   invalidate every cached ID at once. Re-run the introspection
   query (below) after any column edit.

For the adopting project (Airflow), all three values are
declared in
[`../../<project-config>/project.md`](../../<project-config>/project.md#github-project-board).

## Create a board

Setup's board step ([`setup config`](../../plugins/magpie-setup/skills/setup/config.md#step-3a1--project-board-github-trackers))
creates a board only on the operator's explicit yes, and needs the `project` scope on the `gh` token
(`gh auth refresh -s project`). Three mutations, run in order, each shown before it runs:

```bash
# 1. The board, owned by the tracker's owner (an organisation or a user node id).
gh api graphql -F owner=<owner-node-id> -F title="<tracker> security tracker" -f query='
mutation($owner: ID!, $title: String!) {
  createProjectV2(input: {ownerId: $owner, title: $title}) { projectV2 { id number url } }
}'

# 2. Linked to the tracker repository, so its issues can be added.
gh api graphql -F project=<project-id> -F repo=<tracker-repo-node-id> -f query='
mutation($project: ID!, $repo: ID!) {
  linkProjectV2ToRepository(input: {projectId: $project, repositoryId: $repo}) { repository { id } }
}'

# 3. The Status field with the seven lifecycle columns.
gh api graphql -F project=<project-id> -f query='
mutation($project: ID!) {
  createProjectV2Field(input: {projectId: $project, dataType: SINGLE_SELECT, name: "Status",
    singleSelectOptions: [
      {name: "Needs triage", color: GRAY, description: ""},
      {name: "Assessed", color: BLUE, description: ""},
      {name: "CVE allocated", color: PURPLE, description: ""},
      {name: "PR created", color: YELLOW, description: ""},
      {name: "PR merged", color: ORANGE, description: ""},
      {name: "Fix released", color: GREEN, description: ""},
      {name: "Announced", color: PINK, description: ""}]}) {
    projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } }
  }
}'
```

A new board already carries a default `Status` field; when step 3 reports a name clash, add the seven options to that field
instead (`updateProjectV2Field` with the same `singleSelectOptions`), or rename it first.
Record the board's `id`, `number` and `url`, the field `id` and each option's `id` in the
[per-project configuration](#per-project-configuration) and the vetted-ops policy.

## Keep the board security-only

The board lists embargoed trackers, so it holds nothing else and stays private. Three settings keep it that way:

- **Auto-add to project** filters on the security label, as in [the auto-add filter](#auto-add-workflow-filter) (UI only).
- **Auto-add sub-issues to project** is off: it adds sub-issues of anything on the board, whatever their labels (UI only).
- The board's description says what it is for:

```bash
gh api graphql -F project=<project-id> -f desc="Security trackers only" -f readme="<what the board is for>" -f query='
mutation($project: ID!, $desc: String!, $readme: String!) {
  updateProjectV2(input: {projectId: $project, shortDescription: $desc, readme: $readme}) { projectV2 { id public } }
}'
```

Leave `public` out of the mutation: changing a board's visibility, even to private, needs owner rights
(`Viewer not authorized to change project visibility` otherwise). Check `public` is `false` in the result;
if it is not, ask an owner to make the board private.
Keep the text to what the board is for: the public-surface guard refuses the mutation when it names a lifecycle column
such as the allocation stage, and the columns are visible on the board anyway.

The sync enforces the rest: its end-of-sync sweep reads every item (`board-items`) and proposes archiving anything that is not
an issue in the tracker repository carrying the security label.

## Introspection — find the itemId and current column

Run this when the sync skill's Step 1a reads the tracker state. It
returns the `itemId` (needed for the write mutation later) and the
current `Status` column name:

```bash
gh api graphql -f query='
query($n: Int!) {
  repository(owner: "<tracker-owner>", name: "<tracker-name>") {
    issue(number: $n) {
      projectItems(first: 5) {
        nodes {
          id
          project { number }
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                field { ... on ProjectV2SingleSelectField { name } }
                name
              }
            }
          }
        }
      }
    }
  }
}' -F n=<N> \
  --jq '.data.repository.issue.projectItems.nodes[]
        | select(.project.number == <project-number>)
        | {itemId: .id, status: (.fieldValues.nodes[] | select(.name != null)).name}'
```

Substitute the `<tracker-owner>` / `<tracker-name>` / `<project-number>`
values from the project manifest. The query returns one object per
matching project item; if the issue is not on the board yet, the
result is empty and the skill falls back to the *orphan-issue* path
(see below).

## Introspection — re-fetch the option IDs

Run this when the column-option IDs stop working (a write mutation
starts returning `not found`):

```bash
gh api graphql -f query='
query($pid: ID!) {
  node(id: $pid) {
    ... on ProjectV2 {
      field(name: "Status") {
        ... on ProjectV2SingleSelectField {
          id
          options { id name }
        }
      }
    }
  }
}' -F pid=<project-board-node-id> \
  --jq '.data.node.field | {statusFieldId: .id, options: .options}'
```

Update the project manifest's option-ID table with the returned
values. The GraphQL `updateProjectV2Field` mutation replaces the whole
option list rather than editing it in place, so a single column rename
or add regenerates **every** option ID at once.

## Write — move a tracker to a different column

Once the `itemId` is known (from the Step 1a read), move the tracker
by calling `updateProjectV2ItemFieldValue` with the target column's
option ID:

```bash
gh api graphql -f query='
  mutation($pid: ID!, $iid: ID!, $fid: ID!, $oid: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $pid
      itemId: $iid
      fieldId: $fid
      value: { singleSelectOptionId: $oid }
    }) { projectV2Item { id } }
  }' \
  -F pid=<project-board-node-id> \
  -F iid=<itemId from the introspection query> \
  -F fid=<status-field-node-id> \
  -F oid=<option-id of the target column>
```

## Orphan-issue path

If the introspection query returns an empty result, the tracker does
not yet have a project item — typically a freshly-created tracker
that the board's automation has not picked up. Add it to the board
first via `addProjectV2ItemById` using the issue's node ID, then call
`updateProjectV2ItemFieldValue` on the returned item ID:

```bash
# Step 1: get the issue's node ID.
gh api graphql -f query='
query($n: Int!) {
  repository(owner: "<tracker-owner>", name: "<tracker-name>") {
    issue(number: $n) { id }
  }
}' -F n=<N> --jq '.data.repository.issue.id'

# Step 2: add the issue to the project board.
gh api graphql -f query='
  mutation($pid: ID!, $nid: ID!) {
    addProjectV2ItemById(input: { projectId: $pid, contentId: $nid })
      { item { id } }
  }' \
  -F pid=<project-board-node-id> \
  -F nid=<issue-node-id-from-step-1>

# Step 3: move the newly-added item to the target column (see the write recipe above).
```

## Archive a board item — terminal-state cleanup

When a tracker reaches the terminal `closed` state of the lifecycle
(Step 15 of [`../../README.md`](../../README.md) — CVE record moved
to `PUBLIC`, tracker closed), the project-board item is no longer
useful as an active-work signal. Archive it from the board so the
active columns reflect only in-flight trackers.

Archiving is an explicit Projects V2 mutation (`archiveProjectV2Item`)
that hides the item from the default board view. The item is *not*
deleted — it stays on the board's "Archived items" view and continues
to belong to the project.

### Archive recipe

```bash
gh api graphql -f query='
  mutation($pid:ID!,$iid:ID!) {
    archiveProjectV2Item(input: { projectId: $pid, itemId: $iid }) {
      item { id }
    }
  }' \
  -F pid=<project-node-id> \
  -F iid=<item-id>
```

The `pid` is the same `<project-node-id>` used by the column-move
mutation in [*Write — move a tracker to a different column*](#write--move-a-tracker-to-a-different-column);
the `iid` is the same `<item-id>` returned by the introspection
query (or freshly captured at apply time after `addProjectV2ItemById`
on a previously-orphan issue).

### Idempotency

Archiving an already-archived item returns success without changing
state — the mutation is idempotent on the second call. Skills that
re-run on closed trackers (for example, a backfill sweep on
historically-closed issues) can call `archiveProjectV2Item` without
detecting prior-archived state first.

To detect whether an item is already archived (e.g. before a sync run
to avoid emitting a no-op log line), include `isArchived` in the
introspection query — when an item carries `isArchived: true`, skip
the archive call.

### Inverse — unarchive

If a tracker is reopened (rare; usually only when a closing
disposition is reverted), restore the item to the active board with:

```bash
gh api graphql -f query='
  mutation($pid:ID!,$iid:ID!) {
    unarchiveProjectV2Item(input: { projectId: $pid, itemId: $iid }) {
      item { id }
    }
  }' \
  -F pid=<project-node-id> \
  -F iid=<item-id>
```

The unarchived item lands back on whatever column its `Status` field
points at; if the column needs to change too, follow with a regular
column-move mutation.

## When the board is a no-op

Not every GitHub-backed project runs a Projects V2 board. A project
that lists its trackers via plain issue lists or milestones can leave
the board-related fields in its manifest empty; sync-style skills
should treat missing board config as *"no board reconciliation to do"*
and skip the board-column proposal without failing the sync.
