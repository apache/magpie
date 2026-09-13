<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Pool selection — picking the candidate set

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 1:
choosing which issues to sweep.

Selection drives campaign quality. A narrow, bounded slice produces
useful findings; an unbounded sweep produces noise.

## Pool taxonomy

Adopters declare named pools in
[`<project-config>/reassess-pool-defaults.md`](../../../../projects/_template/reassess-pool-defaults.md).
Common pools across projects:

| Pool | Surfaces |
|---|---|
| `open-eol` | Silent fixes (long-fixed but never closed) + real bugs that fell through the cracks at end-of-life |
| `reopened` | Persistent wishlists the team has resisted (often `feature-request-disguised-as-bug`); true regressions where a fix didn't stick |
| `stale-unresolved` | Issues with no activity in a long window — useful for hygiene sweeps |
| project-specific | Adopters add pools tuned to their concerns (e.g. issues missing a component, issues filed before a specific release) |

The skill picks one pool per campaign; the user can override per-
invocation with `reassess pool:<name>`.

## Pool-selection heuristics

Different pools over-represent different verdict natures. Pick the
pool deliberately based on what the campaign is hunting for.

**Hunting silent fixes** — issues the team probably fixed
incidentally but didn't close. Use `open-eol` (or analogous
project-specific pool). The signature: bugs filed against a
version that was end-of-life'd, refactored, or fundamentally
changed; the underlying fix often arrived via the refactor itself.

**Hunting wishlists** — long-lived feature requests the team has
resisted re-considering. Use `reopened`. The signature: an issue
that was closed (often as won't-fix or by-design), then re-opened
by someone arguing for it. Frequently classifies as
`feature-request-disguised-as-bug` in the nature analysis.

**Hunting true regressions** — bugs that came back after being
fixed. Use `reopened` filtered for closed-then-reopened with a
recent re-open date. The signature: a recent re-open following a
gap of years.

**Hunting documentation gaps** — issues classified
`intended-and-documented` (the behaviour is correct AND the docs
say so), where the reporter still mis-read the docs. The pattern
suggests the docs need a clarifying paragraph. Any pool surfaces
these; `reopened` over-represents them.

**Hunting hygiene candidates** — issues missing a component,
filed against an EOL release, or with no activity in years. Use
the project's `stale-unresolved` or component-absent pool.

## Bounded-sweep discipline

A useful campaign sweeps **5–50 issues**. More is rarely
productive:

- Context exhaustion: a 50-issue sweep with full per-issue
  evidence can fill an agent's context budget. Bound shorter than
  the theoretical maximum.
- Diminishing returns: the first 10 issues from a well-chosen pool
  surface the patterns; the next 40 mostly confirm them.
- Crash recovery: a 200-issue sweep that crashes at issue 150 loses
  150 issues of work even with disk-resumability — re-loading the
  context is non-trivial.

Recommend per-session caps:

| Campaign type | Cap |
|---|---|
| First sweep of a new pool | 5–10 |
| Pattern-confirmation follow-up | 10–20 |
| Sustained periodic campaign | 20–50 |
| Anything > 50 | Split into multiple campaigns with shared `<campaign-id>` |

## Query construction

The pool's query lives in
[`<project-config>/reassess-pool-defaults.md`](../../../../projects/_template/reassess-pool-defaults.md).
Each project declares its own queries against `<issue-tracker>`.

The skill resolves the pool name to a query, runs it, and
truncates to the count cap before presenting candidates.

**Query languages by tracker type** (set in
`<project-config>/issue-tracker-config.md` → `tracker_type`):

- **JIRA**: JQL — issued via the JIRA REST API
  (`<issue-tracker>/rest/api/2/search?jql=...`). Example pool query:
  ```text
  project = <issue-tracker-project> AND resolution = Unresolved
    AND status = Open
    AND fixVersion in unreleasedVersions()
  ORDER BY created ASC
  ```
- **GitHub Issues**: `gh search issues` syntax or the GraphQL
  search endpoint. Example pool query:
  ```text
  is:open is:issue repo:<issue-tracker-project>
    label:"area:scheduler" no:assignee
    created:>2024-01-01
  ```
  GitHub Issues lacks JIRA's `fixVersion` concept — adopters
  typically use `label:` predicates and milestones to slice
  similarly.
- **Bugzilla / GitLab / other**: project-specific; the
  `<project-config>/reassess-pool-defaults.md` file declares the
  exact query language and templates.

**Order**: queries should include `ORDER BY` so candidates come
out in a stable order across runs (typically `created ASC` for
hunting old silent fixes; `updated DESC` for hunting recent
activity; the project's pool definitions choose).

## Echo and confirm

After the query runs, the skill echoes the candidate list to the
user before proceeding to the per-issue loop. This catches:

- A fuzzy filter that included issues the user didn't mean to sweep.
- A query that returned too many candidates (user can cap further).
- An empty result (tell the user and stop; do not silently widen the
  pool).

Sample echo format:

```text
Resolved pool: open-eol
Total candidates: 47 (capped to 10 per default; pass count:N to override)

  <KEY>-9999  | EOL-1.x  | "Reporter title here ..."
  <KEY>-9998  | EOL-1.x  | "Another reporter title ..."
  ...

Proceed? [y / cap-to-5 / cap-to-20 / cancel]
```

## Pool-rotation guidance

For projects running periodic reassess campaigns, rotate pools
across cycles to avoid over-fitting to one shape:

| Cycle | Pool | Why |
|---|---|---|
| 1 | `open-eol` | High silent-fix density; clears the easy wins first |
| 2 | `reopened` | Surfaces the wishlists and regressions hidden by cycle-1's bug-as-advertised majority |
| 3 | `stale-unresolved` | Hygiene; many can close without further investigation |
| 4 | Project-specific | Component-missing, area-specific, etc. |

After 4 cycles, return to cycle 1 and re-run against
`<default-branch>` — new fixes since the prior cycle become
silent-fix candidates this time around.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration; this file expands Step 1.
- [`<project-config>/reassess-pool-defaults.md`](../../../../projects/_template/reassess-pool-defaults.md) —
  per-project named-pool queries.
- [`<project-config>/issue-tracker-config.md`](../../../../projects/_template/issue-tracker-config.md) —
  tracker URL, project key, query syntax declaration.
- [`per-issue-flow.md`](per-issue-flow.md) — what happens to each
  candidate after pool selection.
