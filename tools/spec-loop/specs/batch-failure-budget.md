<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Per-item failure budget and harness-outage exclusion for batch skills
status: experimental
kind: feature
mode: infra
source: >
  Observed in the batch (sweep) skills: issue-triage, security-issue-triage,
  issue-stale-sweep, pr-stale-sweep, good-first-issue-sweep and
  issue-reassess.
  Each documents "stop and surface" as the response to any per-item error,
  so one bad item sinks a whole sweep and a forge outage reads as a failure
  of every item. To be implemented as a shared contract in
  docs/batch-failure-budget.md, a shared prose block under tools/dev/blocks/,
  the per-skill Failure modes tables, and (for pr-management-triage) in
  tools/pr-management.
acceptance:
  - A failure on one item of a batch skill's read or classify phase records
    that item as failed and the sweep continues with the next item.
  - Each batch skill declares a per-item failure budget; when it is
    exhausted the sweep stops, says why, and lists every item it did not
    reach.
  - Write-phase failures (a post, label or close that fails mid-loop) keep
    the existing stop-and-surface behaviour; the budget never causes a
    write to be retried.
  - Harness failures (outage, rate limit, auth expiry, network timeout)
    are classified as such, do not count against any item's budget, and
    trip a separate consecutive-failure breaker that stops the sweep as
    "harness outage, nothing counted against items".
  - The recap distinguishes item failures from harness failures and gives
    the selector that reruns exactly the unfinished items.
  - The exclusion ships only together with the budget, never alone.
---

# Per-item failure budget and harness-outage exclusion for batch skills

## What it does

Lets a sweep over many tracker items survive one bad item, and lets a
forge outage during a sweep be reported as an outage rather than as a
failure of every item it touched.

Today every batch skill's Failure modes table says the same thing for a
per-item error: *stop, surface the failed item, instruct the user to
retry*. That is the right answer for the **write** phase, where a retry
risks a second comment or label on the same item, which is exactly what
makes contributors distrust bots. It is the wrong answer for the **read
and classify** phase, where one issue with a missing body, an unparsable
timestamp or a tracker 500 aborts a sweep of two hundred and leaves the
maintainer with nothing. And because every failure is a stop, there is no
way to tell "this item is bad" from "the API is down": an outage halfway
through a sweep reads as a failure at whatever item happened to be next.

This spec is a two-step change, proposed together because the second
step is meaningless without the first:

1. **Per-item failure budget.** Each item of the read/classify phase is
   wrapped so a failure records the item as `failed` with its reason and
   the sweep moves on. A skill-declared budget bounds how many such
   failures a sweep tolerates before it stops. The budget stops a sweep
   whose inputs are systematically broken; it does not hide failures,
   every one is in the recap.
2. **Harness-outage exclusion.** Failures are classified before they are
   counted. An *item* failure (bad or missing data on that item) consumes
   the budget. A *harness* failure (the forge or model backend is
   unavailable, rate limited, or the session's auth expired) does not; it
   is counted on a separate consecutive-failure breaker. When the breaker
   trips the sweep stops with "harness outage" and **no** item is marked
   failed for it, so a rerun after the outage picks those items up as
   simply unfinished.

## Where it lives

Step 1, the per-item budget, has shipped; step 2, the harness-outage
exclusion, has not.

- `docs/batch-failure-budget.md`: the shared contract: the two phases, what
  counts as an item failure, the budget values, the recap.
- `tools/dev/blocks/item-failure-budget.md`: the shared prose block
  (`## Item failure budget`) that `check-shared-blocks.py` propagates into
  the batch skills: `issue-triage`, `security-issue-triage`,
  `issue-stale-sweep`, `pr-stale-sweep`, `issue-reassess` (each before its
  *Failure modes* section) and `good-first-issue-sweep` (before its write
  step). Two skills this spec once listed are not batch sweeps in this
  sense: `contributor-activity-sweep` builds one contributor's card, with
  no pool to budget, and `pr-management-triage` reads its whole pool in
  one paginated query, so there is no per-item read to budget.
- `item_failure_budget` in the config the skill already reads:
  `issue-tracker-config.md`, `project.md` (security), and
  `pr-management-config.md`, each with the default in
  `plugins/magpie-setup/templates/`.
- `tools/pr-management/src/pr_management/failure_budget.py`: the parser and
  accounting; `stale_sweep/classify.py` records an unreadable node
  (`load_with_failures`) or an unclassifiable PR as `failed`, stops before
  the next PR once the budget is exceeded, and reports `failed`, `budget`,
  `unfinished`, `stopped` and `rerun_selector`. `pr-management-config.md`'s
  key is read into `Config.item_failure_budget`.
- `tools/skill-evals/evals/<skill>/item-failure-budget/`: four cases per
  skill: one unreadable item, budget exhausted, a write failing mid-loop,
  a malformed budget value.

## Behaviour & contract

- **Two phases, two rules.** The read/classify phase (fetch the item,
  gather state, classify, draft) is budgeted. The write phase (post,
  label, close, transition) keeps stop-and-surface: a failed write is
  never retried by the skill, because a retry can duplicate a visible
  action. The recap names the failed write and the exact selector to
  resume from the next item.
- **Item failure.** The item's own data made the step impossible: body
  missing, timestamp unavailable, malformed metadata, a 404 or 410 for
  that item, a 403 for that item that the harness check below does not
  explain, a classifier that returned no verdict for that item twice.
  Recorded as `failed` with a one-line reason; the item is skipped for
  the rest of the sweep.
- **Budget.** `item_failure_budget` is either an absolute count or a
  percentage of the pool, whichever the config states; the framework
  default is `max(3, 10% of pool)`. When the count of item failures
  exceeds it the sweep stops before the next item, prints the failures so
  far and the unfinished items, and exits non-zero. The existing
  `over_cap`, security-screen and empty-pool stops are unchanged and are
  not failures.
- **Harness failure.** The failure is about the connection, not the
  item: HTTP 429 or a rate-limit body (a 403 whose body says rate limit
  is this case), HTTP 5xx, connection reset or timeout, a 401 on an
  endpoint that worked earlier in the run, a 403 only when the pre-flight
  auth check, re-run straight after it, fails too, or the model CLI
  exiting non-zero with no output. A 403 alone is not
  enough: GitHub also returns it for one item the token cannot read (a
  hidden or restricted item, a repository the app is not installed on),
  and three such items in a row would otherwise trip the breaker as a
  false outage with none of them recorded as failed. The item is
  **not** marked failed and the budget is **not** consumed. The sweep
  waits one back-off interval and retries that item once.
- **Breaker.** `harness_failure_breaker` consecutive harness failures
  (default 3) stop the sweep as "harness outage". The recap lists the
  items not reached as unfinished, with no failure attached, and the
  rerun selector. A single successful item resets the consecutive count.
- **Recap.** Always three groups: completed (with their dispositions),
  failed items (each with its reason), unfinished (budget exhausted,
  breaker tripped, or write-phase stop; the reason is stated once at the
  top of the group). Then the selector that reruns exactly the failed
  and unfinished items. `N items skipped by security screening` stays its
  own line as today.
- **No silent degradation.** A sweep that hit any failure says so in its
  first recap line. A sweep with zero failures does not mention the
  budget.
- **Order of landing.** The budget lands first, on every batch skill,
  with its eval cases. The exclusion lands second and may land per skill,
  but never before that skill has the budget: without a budget there is
  nothing for the exclusion to exclude from.

## Out of scope

- Retrying writes. A failed post, label or close is surfaced, never
  re-attempted by the skill.
- A cross-skill scheduler or queue. Each sweep is one invocation.
- Detecting an outage before the sweep starts. Pre-flight already checks
  auth and reachability once; this spec covers failures that begin
  mid-sweep.
- Skills that act on one item (`issue-fix-workflow`, `issue-reproducer`,
  `pr-management-code-review`). They have no pool to budget.

## Acceptance criteria

1. In each batch skill, a fixture where one item's body is missing yields
   a recap with that item under *failed* and every other item completed.
2. In each batch skill, a fixture with more item failures than the budget
   stops the sweep, lists failed and unfinished items separately, and
   gives a selector that covers exactly those items.
3. A fixture where a post fails mid-loop in the write phase still stops
   immediately, names the item, and does not retry (unchanged behaviour,
   pinned).
4. With the exclusion: a fixture where the tracker returns 429 for three
   consecutive items stops the sweep as a harness outage, marks no item
   failed, and leaves the budget untouched in the recap.
5. With the exclusion: a single 5xx followed by a successful retry of the
   same item completes that item and consumes no budget.
6. With the exclusion: a 403 on one item while the pre-flight auth check
   still passes records that item as `failed` and does not advance the
   breaker; three such items in a row do not stop the sweep as an outage.
7. `tools/pr-management` carries the budget and the classifier in code
   with pytest coverage; `skill-and-tool-validate` passes; every touched
   `SKILL.md` has its `measured_tokens` restamped and its eval suite
   extended.
8. The exclusion is never present in a skill whose budget is absent.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/pr-management --group dev pytest
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/issue-triage/
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/good-first-issue-sweep/
python3 tools/dev/check-shared-blocks.py
uv run --project tools/spec-validator --group dev spec-validate
```

## Known gaps

- **Step 2, the harness-outage exclusion, is not built.** The plan carries
  it as `harness-outage-exclusion`.
  <!-- gap-closes-when: none (narrative) -->
- **`pr-management-triage`'s batch writes do not stop on a failed write.**
  Its interaction loop documents that a failure in a batched action does not
  cascade-abort: the per-PR error is logged and the batch continues. That is
  the opposite of this contract's write rule. Whether triage's per-group
  batches should follow it is a maintainer decision, left unchanged here.
  <!-- gap-closes-when: none (narrative) -->
- **Only `pr-stale-sweep` has the budget in code.** The other five apply
  it from the prose block; their reads are agent-driven, so there is no
  deterministic loop to put it in.
  <!-- gap-closes-when: none (narrative) -->
- The rate-limit and auth error shapes differ per forge (GitHub, GitLab,
  Forgejo, Jira, Bitbucket). The classifier belongs behind the tracker
  capability contract in `tools/tracker/`, so each adapter maps its own
  status codes to the two classes; this spec does not pin the per-adapter
  tables.
