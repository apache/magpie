<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Delivering the maintainer-triage note

Every contributor-facing action delivers its text the same way.
The body is rendered, never written by hand: the renderer substitutes every placeholder, keeps the marker strings verbatim, links every `#NNN`, and lets the PR author be the only `@`-mention.

## 0. Optimistic lock

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save liveness-<N>.json gql-pr-liveness <N>
uv run --project <framework>/tools/pr-management pr-management triage guard <action> --pr <N> --head <head_sha> --saved-dir <workspace>/saved
```

`proceed: false` with `reroute: reclassify` → the contributor pushed since the sweep; re-classify the PR (see [`interaction-loop.md#step-4--execute`](../interaction-loop.md#step-4--execute)) before delivering anything.

## 1. Render

```bash
uv run --project <framework>/tools/pr-management pr-management triage render --saved-dir <workspace>/saved \
  --pr <N> --action <action> --row <row> --viewer <viewer> \
  --out-dir <scratch> --details-json <scratch>/pr-<N>-details.json
```

Write the group entry's `details` object from the classify output to `<scratch>/pr-<N>-details.json` first.
The result names the `body_file`, the `channel`, whether to `assign_author` / `unassign_author`, and a `preview`.
Show the maintainer the preview and the channel before the mutation: under `pr-body` the note folds into the description (only the author is notified); under `comment` it posts as a comment (every subscriber is notified).
Never edit the rendered body to add a mention, and never post a `warnings` entry about an unresolved placeholder — fix the config value instead.
To keep a handle live, it goes in the project's `mention_allowlist`, or — when the maintainer asks for it on this one note — `--allow-mention <login>` on the render and `MAGPIE_ALLOW_MENTIONS=1` on the posting command.

## 2a. Channel `pr-body` (default) — fold into the description

Read the current body just before writing, so an author's edit since the sweep is not lost:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save body-<N>.json pr-view-with-body <N>
uv run --project <framework>/tools/pr-management pr-management triage fold --current-body <workspace>/saved/body-<N>.json \
  --block <body_file> --out <scratch>/pr-<N>-newbody.md
gh pr edit <N> --repo <upstream> --body-file <scratch>/pr-<N>-newbody.md
```

`triage fold` removes any existing `pr-triage-fold` span and appends the new one, so the description always carries exactly one current note.

## 2b. Channel `comment`

```bash
gh pr comment <N> --repo <upstream> --body-file <body_file>
```

## 3. Assignment

When the render result says `assign_author: true`:

```bash
gh pr edit <N> --repo <upstream> --add-assignee <author>
```

and `--remove-assignee <author>` when it says `unassign_author: true` (the ready-for-review flip).
No maintainer is ever assigned or `@`-mentioned; the agent-guard `mention` guard enforces it on `gh pr edit --body*` and `gh pr comment`.

## 4. Record

After each PR's mutations:

```bash
uv run --project <framework>/tools/pr-management pr-management triage session record --session <scratch>/triage-session.json \
  --pr <N> --head <head_sha> --action <action> --classification <classification> --terminal
```

## Label names

The commands in these files show the framework's default label strings.
Use the adopter's: the classify output's `config.ready_label`, and the `quality_violations_close` / `suspicious_changes` values in `<project-config>/pr-management-config.md`.
