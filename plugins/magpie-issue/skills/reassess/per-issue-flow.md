<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Per-issue flow — what happens to each candidate

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 3:
the per-candidate work the campaign performs, the hand-off to
`issue-reproducer`, and the nature analysis applied at campaign
level.

## Per-issue procedure

For each candidate from the pool (in order), in sequence:

### 1. Skip-if-resolvable check

Skim recent comments on the issue. Many old issues have a closing
or near-closing comment like:

- *"Fixed in <version>; issue left open by mistake."*
- *"See `<sibling-KEY>`; same root cause."*
- *"Won't fix per dev@ thread `<link>`."*

When such a comment exists, the verdict shortcuts to
`fixed-on-master` (with the citation), `duplicate-of-resolved`, or
`intended-behaviour`-with-citation — no reproduction needed.
Record the shortcut citation in the verdict's `notes` field.

If no shortcut applies, continue.

### 2. Invoke `issue-reproducer`

Call [`issue-reproducer`](../reproducer/SKILL.md) with the
candidate's tracker key. The skill writes the full evidence
package at
`<scratch>/<campaign-id>/<KEY>/` per
[`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md).

Pass through campaign flags:

- `--no-probe` if the campaign-level flag is set (default: probes
  are enabled).
- `--scratch <campaign-root>/<KEY>` so each issue gets its own
  subdirectory.
- `--timeout <seconds>` if the campaign needs to override the
  default.

The reproducer returns:

- A path to the evidence package directory.
- The `classification` (one of the ten labels in
  [`issue-reproducer/verification.md`](../reproducer/verification.md)).
- The reproducer's draft `nature` (the campaign may revise this —
  see Step 3 below).
- Any new-issue candidates from cross-family probes.

### 3. Apply nature analysis

The reproducer writes a draft `nature` field into `verdict.json`
based on what it observed. The campaign-level review can revise
this based on additional context the reproducer didn't have:

- Cross-issue patterns (this reporter has filed five similar
  *feature-request-disguised-as-bug* reports; treat as such).
- Closing-comment evidence (a maintainer commented in 2018 *"this
  is by-design per docs"*; that's `intended-and-documented`).
- Multi-case partial-fix detection (per
  [`issue-reproducer/verdict-composition.md`](../reproducer/verdict-composition.md)
  — if cases are mixed, the nature shifts to
  `bug-as-advertised-partial-fix`).

The five nature labels are documented in
[`issue-reproducer/verdict-composition.md` → *"The nature field"*](../reproducer/verdict-composition.md#the-nature-field).
This skill is where the nature gets *applied* across a campaign;
the reproducer's draft is starting context, not the final answer.

### 4. Per-issue hand-back

After the per-issue verdict is locked, surface to the campaign
orchestrator:

- The path to the evidence package.
- The final `classification` + `nature` pair.
- Any new-issue candidates from probes.
- Any maintainer-citation shortcuts used (so the report can list
  citations).

The orchestrator collects these into the campaign-level aggregate
(see [`verdict-aggregation.md`](verdict-aggregation.md)).

### 5. Reset for next issue

Per [`issue-reproducer/runtime-recipes.md` → *"Working-tree
hygiene"*](../reproducer/runtime-recipes.md#working-tree-hygiene),
the reproducer resets the working tree on its way out. The campaign
shouldn't need to do anything extra here, but it should **verify**
the reset happened before moving on (`git status` clean) —
campaign-scale drift from working-tree leak is hard to debug. (The
`git status` check is the **Git binding** of the framework's
source-control capability
([`tools/github/source-control.md`](../../../../tools/github/source-control.md));
a project on a non-Git VCS enabled under *Tools enabled → Source
control* substitutes that tool's working-tree-status binding.)

## Bulk-mode subagent fanout

For N > 5 candidates, the per-issue loop can fan out via read-only
subagents. The pattern:

1. **Orchestrator** spawns one subagent per candidate in a single
   message, with the candidate's tracker key + the campaign scratch
   path.
2. Each **subagent** is read-only — it invokes
   [`issue-reproducer`](../reproducer/SKILL.md) but does
   **not** post anything, does not write outside its assigned
   `<scratch>/<KEY>/` directory, and does not classify the nature
   (that stays in the orchestrator's context).
3. Each subagent returns:
   - The path to its evidence package.
   - The reproducer's `classification` and `runtime_ms`.
   - The reproducer's draft `nature`.
   - Whether any probe surfaced a new-issue candidate.
4. **Orchestrator** collects results, applies Step 3 nature analysis
   (in its own context, with cross-issue visibility), and writes the
   campaign aggregate.

**Hard rules for bulk mode** (mirrors `security-issue-triage`'s
bulk-mode rules):

- Subagents are read-only on the tracker. Even if a subagent's
  prompt accidentally suggests posting, it must refuse and surface
  the request to the orchestrator.
- Subagents do not classify the nature; the campaign-level view
  (cross-issue patterns) is what makes nature judgement stable.
- The orchestrator runs Step 4–6 of `SKILL.md` (aggregation, report
  composition, hand-back) sequentially in its own context, not in
  parallel.
- If any subagent reports calling a write tool, the orchestrator
  marks the apply phase as *"do not run"* until the bug is
  investigated.

## Skip-list behaviour

The resumability check in `SKILL.md` Step 2 builds a skip list of
candidates whose `verdict.json` already exists for the current
`<default-branch>` rev. The per-issue loop respects this list:

- Skipped candidates: re-use the existing `verdict.json`; no
  reproducer invocation.
- Stale-but-existing candidates (`verdict.json` exists but against
  a different rev): the user-confirmation in Step 2 decided
  refresh-vs-reuse; honour the decision.
- Partial-artefacts candidates: the reproducer is idempotent —
  re-invoking with the same scratch path picks up from
  inventory if `description.md` is present, etc.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration; this file expands Step 3.
- [`issue-reproducer`](../reproducer/SKILL.md) — the
  per-issue skill this loop calls.
- [`issue-reproducer/verdict-composition.md`](../reproducer/verdict-composition.md) —
  the `verdict.json` schema, the nature taxonomy.
- [`verdict-aggregation.md`](verdict-aggregation.md) — what the
  orchestrator does with the collected verdicts.
- [`pool-selection.md`](pool-selection.md) — what the loop is
  iterating over.
