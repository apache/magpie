<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Candidate rules

The two-stage screen that turns the `ready for maintainer review` queue into a
ranked list of quick-merge candidates. Both stages are a **pure function** of
the data fetched in [`SKILL.md` Step 1](SKILL.md#step-1--fetch-the-ready-queue) —
no network calls, no prompts, no writes.

Reading order:

1. [Stage 1 — quality gate](#stage-1--quality-gate) — hard pass/fail. A PR that
   fails any gate is dropped and never reaches Stage 2.
2. [Stage 2 — triviality](#stage-2--triviality) — footprint + path
   allow/deny + tier assignment.
3. [Tiers](#tiers) — what Tier A and Tier B mean.
4. [Path matching](#path-matching) — how globs are evaluated, deny precedence.
5. [Drop-reason taxonomy](#drop-reason-taxonomy) — the auditable reasons a PR
   is excluded (surfaced in the [Step 4 summary](SKILL.md#step-4--session-summary)).
6. [Required fields](#required-graphql-fields) — what the batch query must
   populate.

All thresholds and path lists are read from
[`<project-config>/pr-management-quick-merge-config.md`](../../../projects/_template/pr-management-quick-merge-config.md)
at session start. The values below are the **shape**, not hard-coded constants.

---

## Stage 1 — quality gate

A PR proceeds to Stage 2 only if **every** condition holds. This mirrors the
strict reading of [`pr-management-triage`](../pr-management-triage/classify-and-act.md)
rows 19/20 plus the workflow-approval guard — a quick-merge candidate must be at
least as clean as a PR the triage skill would call `passing`.

| # | Gate | Pass condition |
|---|---|---|
| G1 | Label present | `labels` contains `ready for maintainer review` (guaranteed by the search query; re-checked defensively). |
| G2 | Real CI green | `statusCheckRollup.state == SUCCESS` **and** the [Real-CI guard](../pr-management-triage/classify-and-act.md#real-ci-guard) passes — at least one context matches a `real_ci_patterns` entry, so the SUCCESS is not coming only from `Mergeable`/`WIP`/`DCO`/`boring-cyborg`. |
| G3 | No failed/pending checks | `failed_checks` is empty **and** no context is still `QUEUED`/`IN_PROGRESS`/`PENDING`. A candidate must be *done and green*, not green-so-far. |
| G4 | No workflow approval pending | the PR's `head_sha` is **not** in the per-session `action_required` index. |
| G5 | Not obviously conflicting | **Mergeability is resolved live in [Stage 3](#stage-3--live-merge-readiness), not from the batch.** Stage 1 only early-drops a PR whose *batch* `mergeable == CONFLICTING` (a cheap cull of the obviously-conflicted ~10%). `MERGEABLE` and `UNKNOWN` both pass G5 here and defer to the Stage 3 re-poll — see the note below for why. |
| G6 | No unresolved collaborator threads | zero `reviewThreads` with `isResolved == false` whose first comment's `authorAssociation ∈ {OWNER, MEMBER, COLLABORATOR}`. Contributor-author side threads do not block (same qualifier as triage's [`unresolved_threads_only`](../pr-management-triage/classify-and-act.md#unresolved_threads_only)). |
| G7 | No outstanding changes-requested | no `latestReviews` node with `state == CHANGES_REQUESTED` that is newer than the last commit. |

**Why mergeability is deferred to a live re-poll.** GitHub computes `mergeable`
on demand and caches it only briefly, so a single batched search over a large
`ready` queue returns `mergeable == UNKNOWN` for many PRs and — more
importantly — `mergeStateStatus == BLOCKED` for *most* ready PRs, because branch
protection is withholding the merge pending the required approval they do not
have yet. Gating on the batch values here drops nearly the whole queue
(observed on a real run: **177 of 204** ready PRs dropped on a batch
mergeability gate, almost none of them actually conflicting — they were
`BLOCKED` awaiting a committer approval, which is precisely the case this skill
exists to clear). So Stage 1 only early-drops the batch-`CONFLICTING` PRs; true
merge-readiness — including the `BLOCKED`-on-approval case — is resolved
per-candidate in [Stage 3](#stage-3--live-merge-readiness), after triviality has
narrowed the set to a handful (one REST call each, cheap).

A PR failing G1–G4/G6/G7 is dropped with the corresponding
[drop reason](#drop-reason-taxonomy) (`gate:<Gn>`) and excluded from Stage 2.

---

## Stage 2 — triviality

Of the gate-green survivors, a PR is a quick-merge candidate iff **all** hold:

### 2a. Footprint within budget

- `additions + deletions <= max_churn` (config; default `20`)
- `changed_files <= max_files` (config; default `3`)

`max_churn` counts the PR's own `additions + deletions` totals (not the diff of
the merge). Pure deletions count toward churn — a PR that deletes 40 lines is
not trivial-to-merge just because it adds nothing; deletion can be as
consequential as addition.

### 2b. Every file in the allow-list

For **every** entry in `files.nodes[].path`, the path must match at least one
glob in the active tier's allow-list (`tier_a_allow_globs`, plus
`tier_b_allow_globs` when Tier B is enabled — the default). One file that
matches no allow glob fails the PR with drop reason `path-unmatched`.

### 2c. No file in the deny-list

For **every** entry in `files.nodes[].path`, the path must match **no** glob in
`deny_globs`. One file matching a deny glob fails the PR with drop reason
`path-denied` — **even if it also matches an allow glob, and even if the PR is
one line**. Deny precedence is absolute (Golden rule 3).

A PR passing 2a–2c is a candidate; assign its [tier](#tiers).

---

## Stage 3 — live merge-readiness

Stages 1–2 run over the batch fetch. For each survivor — now a handful, not the
whole queue — resolve mergeability **live**: a direct
`GET /repos/<repo>/pulls/<N>` forces GitHub to compute `mergeable` +
`mergeable_state` fresh, which the batched search value cannot be trusted to
reflect (see the [Stage 1 note](#stage-1--quality-gate)). One REST call per
candidate; cheap because the set is already small.

Classify each candidate by the live `(mergeable, mergeable_state)` pair:

| Live state | Disposition |
|---|---|
| `mergeable == true`, `mergeable_state ∈ {clean, has_hooks}` | **Ready to merge.** Surface in the *ready* bucket with the merge command. |
| `mergeable == true`, `mergeable_state ∈ {unstable, behind}` | **Ready to merge.** `unstable` is a *non-required* check still running/failed (G2/G3 already proved every required check green); `behind` is a stale-but-clean branch GitHub fast-forwards. Surface in *ready*; note the state. |
| `mergeable == true`, `mergeable_state == blocked` | **Needs your approval, then merge.** The branch merges cleanly but branch protection withholds it — and since Stage 1 proved CI green and no changes-requested, the withheld requirement is the **required review**: the PR lacks a qualifying committer approval. Surface in the *approval* bucket and route to the [`[A]pprove`](SKILL.md#step-3b--optional-approve-action) action. **This is the skill's primary case — most ready PRs sit here — not a drop.** |
| `mergeable == false` **or** `mergeable_state == dirty` | **Conflict → drop** (`gate:G5-conflict`). |
| `mergeable == null` / `mergeable_state == unknown` (even after the live call) | **Still computing → drop this run** (`gate:G5-unknown`), conservative per Golden rule 4. It settles and qualifies next run. |

The `blocked` row is the load-bearing change. A ready PR that is trivial,
all-green, and merges cleanly but simply has no committer approval yet is exactly
what the [`[A]pprove`](SKILL.md#step-3b--optional-approve-action) action exists
for; treating `blocked` as a drop (as a naive batch gate does) hides the skill's
whole reason to exist.

**Confirm 'blocked on review', not 'blocked on a required check.'** Stage 1's
G2/G3 already established every check is green and done, so a `blocked` state
here is review-required in the normal case. Where an adopter's branch protection
makes a *non*-CI context required, confirm with
`gh pr view <N> --json reviewDecision` — `REVIEW_REQUIRED` ⇒ a missing approval
is the blocker (route to the approval bucket); any other decision ⇒ drop, the
block is not something an approval clears.

---

## Tiers

| Tier | Meaning | Allow source | Confidence |
|---|---|---|---|
| **A** | Documentation and human-readable text only — `.rst`/`.md` docs, changelog, newsfragments, translations, the spelling wordlist. The change cannot affect runtime behaviour. | `tier_a_allow_globs` | highest — the blast radius is "wrong words on a page" |
| **B** | Low-risk code — test-only files and example/illustration code (example DAGs). No production code path changes. | `tier_b_allow_globs` | medium — still needs a read for assertion correctness, but cannot break production |

A PR is **Tier A** if every file matches a Tier A glob. It is **Tier B** if
every file matches a Tier A *or* Tier B glob and at least one matches a Tier B
glob. (A pure-docs PR is Tier A; a docs + test PR is Tier B; a test-only PR is
Tier B.) `tier:A` on the command line restricts to Tier A only.

Tiers drive **ordering and an honesty signal**, not the gate — both tiers are
surfaced by default. The maintainer reads every diff regardless; the tier tells
them how hard to look (Tier A is usually a glance; Tier B warrants reading the
assertions).

---

## Path matching

- Globs are matched against the **repo-relative POSIX path** in
  `files.nodes[].path` (e.g. `airflow-core/docs/howto/x.rst`).
- Use `**` for any-depth, `*` for single-segment. Matching is case-sensitive on
  the path, case-insensitive on the extension only where the config glob says so.
- **Deny is evaluated before allow and wins.** A path that matches both a deny
  glob and an allow glob is denied.
- A path that matches **neither** list → `path-unmatched` → PR dropped
  (Golden rule 4: unknown paths are not assumed safe).

The default globs live in the
[template config](../../../projects/_template/pr-management-quick-merge-config.md);
the shape for an Airflow-like project:

```text
tier_a_allow_globs:
  - "**/*.rst"
  - "**/*.md"
  - "**/docs/**"
  - "docs/**"
  - "**/newsfragments/**"
  - "**/changelog.rst"
  - "**/i18n/**"
  - "**/locales/**"
  - "**/*.po"
  - "spelling_wordlist.txt"

tier_b_allow_globs:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/example_dags/**"

deny_globs:                 # absolute disqualifiers, even at one line
  - "**/migrations/**"
  - "**/versions/**"
  - "**/alembic*/**"
  - "pyproject.toml"
  - "**/pyproject.toml"
  - "uv.lock"
  - "setup.cfg"
  - "**/requirements*.txt"
  - ".github/**"
  - "**/Dockerfile*"
  - "scripts/ci/**"
  - "**/security/**"
  - "**/auth*/**"
  - "**/jwt*/**"
  - "airflow-core/src/airflow/jobs/**"
  - "airflow-core/src/airflow/models/**"
  - "airflow-core/src/airflow/executors/**"
  - "airflow-core/src/airflow/api_fastapi/**"
  - "airflow-core/src/airflow/serialization/**"
  - "task-sdk/src/airflow/sdk/execution_time/**"
```

The deny-list is the load-bearing safety control and is intentionally broad:
when in doubt, a maintainer adds a path to `deny_globs` rather than risk a
core/security/build path being screened as trivial. A path appearing in both an
adopter's allow and deny lists is a config smell — deny wins, and the validator
should warn.

---

## Drop-reason taxonomy

Every screened-out PR carries exactly one drop reason, surfaced in the
[Step 4 summary](SKILL.md#step-4--session-summary) so the screen is auditable:

| Reason | Meaning |
|---|---|
| `gate:G2` … `gate:G7` | failed the named Stage-1 quality gate (CI red, unresolved thread, changes-requested, …) |
| `too-large` | gate-green but `churn > max_churn` or `files > max_files` |
| `path-denied` | a changed file matched `deny_globs` (consequential area) |
| `path-unmatched` | a changed file matched no allow glob (unknown area) |
| `gate:G5-conflict` | Stage-3 live re-poll: genuine merge conflict (`mergeable == false` / `dirty`) |
| `gate:G5-unknown` | Stage-3 live re-poll: mergeability still uncomputed after the direct call — dropped this run, qualifies next |

`gate:*` and `gate:G5-unknown` drops are reported as a single count each (the
maintainer rarely cares which one a non-ready-looking PR hit); `too-large`,
`path-denied`, `path-unmatched`, and `gate:G5-conflict` are reported with PR
numbers, because those are the "so-close" PRs a maintainer may want to glance at
or hand to `pr-management-code-review`. **Note:** a `BLOCKED` live state is
**not** a drop reason — it is the *approval* bucket (see
[Stage 3](#stage-3--live-merge-readiness)), the skill's primary output.

---

## Required GraphQL fields

Extend the family batch query
([`pr-management-triage/fetch-and-batch.md`](../pr-management-triage/fetch-and-batch.md))
with the fields this screen needs beyond what triage already fetches:

| Stage | Required fields / calls (delta over the triage batch query) |
|---|---|
| Stage 1 | batch `mergeable` (only the `CONFLICTING` early-drop); (`statusCheckRollup`, `reviewThreads`, `latestReviews`, `head_sha` already present) |
| Stage 2 | `additions`, `deletions`, `files(first: 100) { nodes { path additions deletions } }` |
| Stage 3 | **one REST call per surviving candidate** — `GET /repos/<repo>/pulls/<N>` for live `mergeable` + `mergeable_state`; plus `gh pr view <N> --json reviewDecision` only when disambiguating a `blocked` state |

Everything else (label list, author association, rollup contexts, the
`action_required` index) is already fetched by the shared family machinery.
Golden rule 6 ("one query per page") still applies to the Stage-1/2 batch — the
`files` connection rides along in the same paged call. Stage 3's per-candidate
REST calls are deliberately **not** batched: they are the unavoidable cost of
forcing GitHub to compute mergeability, and they run only on the small
post-triviality survivor set, not the whole queue.

> **Note — `mergeStateStatus` from the batch is no longer gated on.** Earlier
> drafts gated Stage 1 on the batch `mergeStateStatus`; that dropped ~87% of a
> real `ready` queue because GitHub reports `BLOCKED`/`UNKNOWN` for most ready
> PRs in a batch. The batch value is now informational only; Stage 3's live
> re-poll is authoritative.
