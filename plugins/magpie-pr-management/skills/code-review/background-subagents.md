<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Background analysis subagents

## Why

Step 2 (`gh pr view` + `gh pr diff` + per-tree `AGENTS.md`
discovery) and Step 4 (line-by-line classification against the
criteria source files) together dominate the per-PR
wall-clock cost. While the maintainer is reading the current
PR's draft, those steps can run for the *next* PRs in
parallel — when the maintainer reaches them, the package is
already drafted and only Step 5 (when a tool-path adversarial
reviewer is configured), Step 6 (disposition pick) and Step 7
(confirmation) are left to run.

The maintainer never sees the subagents directly. They run
silently in the background; their output is what powers the
"instant headline" experience.

## When to fire

After the working list is resolved (Step 1 of `SKILL.md`), and
again after each PR is posted or skipped (Step 9 above), the
parent skill keeps a **lookahead window** of size `K` filled
with in-flight subagents.

```text
queue: [N0_current, N1, N2, N3, N4, N5, ...]
        ^foreground   ^^^^^^^^^^^   ^prefetched (K=3)
                       lookahead
```

Default `K` is **3**. Tune via `lookahead:<N>` at session start
or disable entirely with `no-prefetch`.

Subagents are launched with `run_in_background=true` so the
parent does not block; the parent picks up their results when
the maintainer reaches the corresponding PR (or earlier, if
several finish before the maintainer is done with the current
one — that's fine, the results just sit in memory).

## Subagent contract

Each subagent is a `general-purpose` Agent invocation. The
prompt is **self-contained** (no shared conversation context)
and includes:

- **Inputs** — the PR number, the target repo, the maintainer's
  GitHub login (for the self-review guard), the working
  directory path so the subagent can read the criteria source
  files locally, AND the **pre-fetched PR payload inline in
  the prompt**: the JSON metadata blob, the unified diff, and
  the unresolved-review-threads JSON. The parent runs `gh pr
  view`, `gh pr diff`, and the review-threads GraphQL query
  itself before invoking the subagent and embeds the raw
  output in the prompt.

  Why pre-fetch in the parent: in many harness configurations
  subagents do **not** inherit the parent session's Bash
  permission grants for `gh` — they start a fresh permission
  context and are denied. Embedding the data inline lets the
  subagent run with Read-only tool access (the criteria files
  are already on disk) and removes the permission failure
  mode entirely. The parent's `gh` calls are cheap (3 per PR)
  and run in parallel with the maintainer's confirmation of
  the *previous* PR — no wall-clock cost.

- **Task** — walk every category of findings against
  [`criteria.md`](criteria.md), produce the structured
  package below. The subagent does NOT need to (and should
  not try to) hit GitHub itself.
- **Output schema** (exact, parseable by the parent):

  ```text
  HEAD_SHA: <head_oid>

  ## Headline
  PR #<N> — <title>
    Author: <login> (<assoc>)
    Base: <base> • Head: <head_short>
    CI: <state> • Threads: <unresolved> unresolved • Reviews: <summary>
    Files: <N> changed +<add> -<del>
    Labels: <comma-list>

  ## What it does
  <one-paragraph plain-English summary>

  ## Findings
  <YAML list per the schema in review-flow.md Step 4, or "none">

  ## Suggested disposition
  APPROVE | REQUEST_CHANGES | COMMENT — <one-line reason>

  ## Summary line
  <the one-sentence summary for render --summary>
  ```

- **Forbidden** — the subagent may NOT:
  - call `gh pr review`, `gh pr merge`, `gh pr edit`,
    `gh pr comment`, `gh issue comment`, or any GitHub
    write-mutation command;
  - call any `mcp__github__*` `create_*` / `update_*` /
    `add_*` / `merge_*` mutation;
  - modify any file in the working tree (no `Write`,
    `Edit`, no `git` write commands);
  - invoke other Agents (no nested subagents);
  - **write a review body.** The parent composes the body with
    `code-review render` from the subagent's findings and summary
    line, so the footer and the handle escaping are never left to
    a subagent's paraphrase.

  Posting is reserved to the parent skill, gated by maintainer
  confirmation. Subagents are pure read-and-think workers.

- **Skip-reason short-circuits** — if the subagent's first
  fetch shows the PR is closed, merged, drafted, or authored
  by `<viewer>`, it returns `SKIP: <reason>` instead of a
  package. The parent skill skips the PR with that reason
  attached to the session summary.

## Folding subagent output into Step 1

When the maintainer reaches a prefetched PR, the parent skill:

1. **Compares head SHA** between the subagent's snapshot and
   the live PR. If different, the analysis is stale — by
   default re-fire a fresh subagent before showing anything.
   The maintainer can opt to see the stale draft anyway via
   `[P]ost-anyway` after the parent surfaces the SHA delta.
2. **Renders the package**: runs `context` (cheap — the reads
   are saved), `disposition` and `render` over the subagent's
   findings, and shows the Step 1-through-7 block without
   re-reading the diff.
3. **Holds at Step 7's confirmation gate** identically to the
   no-prefetch path. The only thing different is the source
   of the draft; the maintainer's interaction is unchanged.

## Wasted prefetch — accept it

If the maintainer `[S]kip`s a prefetched PR, the subagent run
was wasted. That's acceptable — the cost of an unused
subagent is small compared to the wall-clock savings on the
cases where the maintainer engages. Don't try to be clever
about "will the maintainer skip this one?" — just keep the
window full.

## Concurrency cap

Don't run more than `K` subagents at once (default `K=3`).
Each subagent issues 2–3 `gh` calls and reads ~5 source
files; `K=3` keeps GitHub-API and file-IO load well under
the maintainer's hourly quota while giving instant headlines
on the next 3 PRs.

If the maintainer's queue is very small (`max:1`–`max:2`),
the wall-clock benefit is nil and the cost of lookahead is
pure waste — pass `no-prefetch` to disable. The skill auto-
disables prefetch when only one PR remains.

## Disagreeing with the subagent

The subagent's draft is **advisory**. The parent skill — and
the maintainer — are free to reject or rewrite it before
posting. If the parent agent reading the package thinks the
subagent missed something material, raise it explicitly to
the maintainer at Step 6 ("subagent suggested APPROVE; I'd
downgrade to COMMENT because…") rather than silently
overriding. Disagreements between the two layers are signal
the maintainer should see, not noise to be smoothed over.

---
