<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# optimize-skill — optimization passes

The five passes [`SKILL.md`](SKILL.md) applies, each distilled from a
landed refactor of the security-skill suite. For every pass: the
**smell** that triggers it (the read-only diagnostic), the
**exemplar** PR that proved it, the **mechanics**, the
**behavior-preservation guarantee**, and the **validation** that
confirms it landed cleanly.

Passes are ordered by blast radius — a pure file move is safer than a
content lift, which is safer than rewiring how a step executes. Apply
in this order so the reviewable diff stays small and each step is
independently revertible.

---

## 1. Split — slim an oversized `SKILL.md` into linked siblings

**Smell.** `SKILL.md` exceeds the 500-line P15 cap, or one section
dominates the body. Diagnostic: `wc -l SKILL.md`; flag `> 500`, and
note the largest `##` sections as split seams.

**Exemplar.** `refactor(security-issue-sync): extract 4 subdocs to
slim SKILL.md 3425 → 658 lines` (#410) — "same pattern as
setup already [uses]. No behavior change — pure file
restructure. Validator stays green." It lifted `gather.md`,
`signals-to-actions.md`, `apply-and-push.md`, and `bulk-mode.md` out
of the body.

**Mechanics.**
1. Identify cohesive, self-contained section clusters (a phase of the
   workflow, a long reference table, a mode variant) that the body
   can reference rather than inline.
2. Move each cluster **verbatim** into a sibling `<topic>.md` next to
   `SKILL.md`. Use cut-and-paste of the exact bytes; do not re-flow
   or paraphrase.
3. Replace the moved region in `SKILL.md` with a one-line pointer to
   the new sibling (e.g. *"… per `gather.md`."*, as a real link).
4. Keep the orchestration — Step 0, the step skeleton, Hard rules,
   the gates — in `SKILL.md`. Only the elaboration moves out.
5. Regenerate the doctoc TOC if the body's headings changed.

**Behavior-preservation guarantee.** The concatenation of the slimmed
`SKILL.md` plus the new siblings contains the same instruction bytes
as the original body. A `git diff` shows deletions in `SKILL.md`
matched by identical additions in the siblings, plus the new pointer
lines — nothing else.

**Validation.** Validator green; `SKILL.md` now under 500 lines;
every sibling linked exactly one level deep from `SKILL.md`; no
unreferenced sibling left behind.

---

## 2. Config-lift — move concrete values into `<project-config>`

**Smell.** Adopter-specific values are baked into the skill body: a
concrete repo slug, a real mailing-list address, a real CVE ID, a
project-specific label or milestone name — anything that should
resolve from `<project-config>/project.md` at runtime instead of
living in the skill. Diagnostic: run the placeholder linter
([`tools/dev/check-placeholders.sh`](../../../../tools/dev/check-placeholders.sh))
and scan for hardcoded strings outside `example:` markers.

**Exemplar.** `feat(security): config-driven lifts of 6 skills`
(#386) and the CVE-authority / forwarder-relay / mail-archive
sub-tool extracts (#388, #387) — project-specific knobs lifted into
the manifest's *Security workflow configuration* block so the skill
body reads them through placeholders.

**Mechanics.**
1. For each concrete value, add (or reuse) a knob in
   `<project-config>/project.md` with a `#` comment stating what it
   controls, the ASF default, when a non-ASF adopter overrides it,
   and the consuming skills.
2. Replace the literal in the skill body with the placeholder /
   manifest-resolved reference.
3. Where the lifted logic is more than a value — a whole adapter
   contract — extract it into a `tools/<name>/` adapter the skill
   resolves at runtime (the #387/#388 sub-tool shape).

**Behavior-preservation guarantee.** For the reference adopter the
resolved value is identical to the literal it replaced. The skill
does the same thing; it now reads the value from config instead of
carrying it. Swapping projects becomes a config change, not a code
change (Principle 13).

**Validation.** Placeholder linter green; the reference adopter's
manifest supplies every newly-referenced knob; validator green.

---

## 3. Out-of-context — read/PATCH a field without loading the body

**Smell.** A step pulls a whole issue body, a rollup comment, or
another large artefact into the agent context only to read or rewrite
**one field** of it. The full text enters the context window (token
cost + a re-injection surface) for a single-field edit.

**Exemplar.** `feat(github-body-field): tool to rewrite one
issue-body field without loading the body into agent context` (#412)
and `feat(github-rollup): append helper for status-rollup comments —
read/PATCH out of context` (#424). Both move a body/​comment mutation
behind a deterministic tool that fetches, edits one field, and writes
back without the body ever entering the agent context.

**Mechanics.**
1. Identify the single field / append the step actually needs.
2. Route the read-modify-write through the existing tool —
   [`github-body-field`](../../../../tools/github-body-field/README.md)
   for one `### Field` section,
   [`github-rollup`](../../../../tools/github-rollup/README.md) for the
   status-rollup comment.
3. Replace the in-context fetch-then-edit prose with the tool call;
   keep the *decision* about what to write in the skill, the
   *mechanics* of writing it in the tool.

**Behavior-preservation guarantee.** The field ends up with the same
value; only the path it took changed. What the skill proposes to the
human and what lands on the tracker are identical — the body simply
never enters the context window.

**Validation.** Validator green; the step's proposal/apply surface
unchanged; a measurable drop in context loaded for that step.

---

## 4. Fetch-upfront — batch per-item round-trips into one pass

**Smell.** The skill issues N sequential fetches (one per candidate
issue / thread / PR) where a single upfront query would return the
whole working set. Latency and API-call budget scale with N for no
analytical reason.

**Exemplar.** `feat(security-issue-triage): fetch-all-upfront pattern
(PR #346 analogue)` (#347) — collect the full candidate set in one
pass, then iterate over the in-memory result instead of round-tripping
per item.

**Mechanics.**
1. Find the per-item fetch loop.
2. Replace it with a single upfront query (or the smallest number of
   batched queries) that returns the whole set, honouring the
   validator's `--limit` requirement on list calls (#359).
3. Iterate over the fetched set; the per-item *analysis* stays
   per-item, only the *fetching* batches.

**Behavior-preservation guarantee.** The set of items processed and
the per-item decisions are unchanged; only the number of round-trips
drops. Guard against the batch hitting a page cap — surface a "count
may be a floor" warning rather than silently truncating.

**Validation.** Validator green (including the `--limit` check); same
items processed; fewer calls.

---

## 5. Preflight-classifier — skip obvious no-ops before LLM passes

**Smell.** The skill spends an LLM pass per item even though a cheap
deterministic check could classify many of them as obvious no-ops
(idle, already-handled, out-of-window) up front. Probabilistic effort
is spent on what executable code already decides (Principle 6).

**Exemplar.** `feat(security-issue-sync): pre-flight no-op classifier
skips obvious-idle trackers in bulk mode` (#414) and `tune pre-flight
classifier — skill-marker detection + relaxed rules` (#416) — a
deterministic classifier (see
[`tools/preflight-audit`](../../../../tools/preflight-audit/README.md))
runs first and drops items that need no work, so the LLM pass only
sees the candidates that actually require judgment.

**Mechanics.**
1. Identify the deterministic signals that mark an item as a no-op
   (recent human activity, a skill-written marker, closed-and-aged,
   bot-only activity).
2. Run the classifier (existing tool or a small new one) as a Step-0
   / pre-flight filter; record per-item the reason it was kept or
   skipped in the observed-state bag.
3. Feed only the survivors to the probabilistic pass.

**Behavior-preservation guarantee.** Items the classifier skips are
exactly those the LLM pass would also have classified as no-ops — the
classifier is tuned conservatively so a borderline item is *kept*,
not skipped. The final decisions on real candidates are unchanged;
the wasted passes disappear. Log what was skipped and why (no silent
truncation).

**Validation.** Validator green; the classifier's skip set is a
subset of what the full pass would no-op; replay/eval fixture
exercises the classifier rules (the #423 pattern).

---

## When a pass is *not* an optimization

Each guarantee above draws the same line: a pass may change **how** a
skill runs, never **what** it decides or proposes. If applying a pass
would change the items processed, the values written, or the prose a
human signs off on, it is a behavior change — stop, and route it
through normal skill editing and review, not this skill. The
green-before / green-after validator gate plus the per-pass
behavior-preservation check are what keep that line honest.
