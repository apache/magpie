<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Bulk mode — syncing many issues in parallel

> Extracted from [`SKILL.md`](SKILL.md) so a bulk run loads only this slice.

---

## Bulk mode — syncing many issues in parallel

In **bulk mode** (triggers in [`SKILL.md`](SKILL.md#bulk-mode--syncing-many-issues-in-parallel)) a **separate subagent** assesses each issue in parallel,
and the orchestrator merges the results into one proposal the user confirms once.
Subagents keep the per-issue mail threads, PR diffs and comment bodies out of the main context.

### Orchestrator responsibilities

1. **Pick the issue list.** Resolve the user's selector into concrete issue numbers before spawning subagents.
   Selectors, in order of precedence:

   | User input | Resolves to |
   |---|---|
   | `sync all` | every open issue in `<tracker>` **plus recently-closed trackers still awaiting a post-close cve.org publication check**. Resolve as: `gh issue list --repo <tracker> --state open --limit 100 --json number,title,labels` ∪ `gh issue list --repo <tracker> --state closed --label "announced" --limit 50 --json number,title,labels,closedAt --jq '[.[] \| select(.closedAt > (now - 90*86400 \| todate))]'`, then **drop any issue labelled `rejections-ledger`** (see below). The closed bucket is the last 90 days of `announced` trackers — those awaiting cve.org propagation, the final reporter notification and the release manager's security-pages checklist item (see [1g](gather.md#1g-recently-closed-trackers--check-cveorg-publication-state)); other closed issues are no-ops and excluded. |
   | `sync all open` | explicit open-only variant — `gh issue list --repo <tracker> --state open --limit 100 --json number,title,labels`, then **drop any issue labelled `rejections-ledger`**. No closed trackers. |
   | `sync #212`, `sync 212`, `sync #212, #214, #218`, `sync #212-#218` | the issue number(s) verbatim. Works on open and closed trackers (the closed-issue sub-steps run when the tracker is closed with `announced`). |
   | `sync CVE-2026-40913` or `sync CVE-2026-40913, CVE-2026-40690` | regex-validate each token against `^CVE-\d{4}-\d{4,7}$` first (a non-match is a hard error — *never* interpolate an unvalidated free-form string into the double-quoted search arg, which would expand `$(...)`); then look up each validated CVE ID with `gh search issues "CVE-YYYY-NNNNN" --repo <tracker> --json number,title,body --jq '.[] \| select(.body \| contains("CVE-YYYY-NNNNN")) \| .number'` (match against the body's *CVE tool link* field) and expand. |
   | `sync <free-text>` (e.g. `sync JWT`, `sync KubernetesExecutor`) | title-substring match — run `gh issue list --repo <tracker> --state open --search "<free-text> in:title" --limit 100 --json number,title` and surface the matches for confirmation (the fuzziest selector — always confirm, never auto-dispatch). |
   | `sync <label>` (e.g. `sync announced`, `sync pr merged`) | all open issues carrying that label — `gh issue list --repo <tracker> --state open --label "<label>" --limit 100 --json number,title`. |
   | `sync announced` (as a label selector) | as above, open-only. To include the recently-closed `announced` bucket, use `sync all` (default) or `sync closed announced`. |
   | `sync closed announced` | the recently-closed `announced` bucket alone — the cve.org publication-check sweep without open issues (e.g. a post-release cron). |
   | `sync open` | alias for `sync all open`. |
   | `sync closed` | open *and* **all** closed issues (not just recent `announced`). Explicit request only — most sync actions are no-ops on closed issues outside the `announced` bucket. |

   Selectors combine: `sync #212, CVE-2026-40690, JWT` resolves each independently and dispatches the union.
   After resolving, **echo the final list back to the user and ask for confirmation** before spawning subagents —
   it catches fuzzy-match surprises (an unintended title hit, a CVE alias matching two scope trackers) before they cost a round-trip.
   When both buckets contribute, group them in the echo: *"9 open, 2 recently-closed awaiting cve.org"*.

   When the selector resolves to zero issues, tell the user and stop — do not fall back to `sync all`.

   When a list call returns exactly its `--limit` (100, or 50 for the closed bucket), the set may be truncated.
   Say so in the echo (*"the list hit the 100-issue cap — the set may be incomplete"*) and offer to re-run with a larger `--limit` before dispatching;
   never sweep a capped list silently.

   **Exclude the rejections ledger.** The single open issue labelled `rejections-ledger` (written by `security-issue-import`) is **not** a security tracker:
   it has no scope label and holds only rejection-record comments.
   Drop it from every set-valued selector (`sync all`, `sync all open`, label/title sweeps);
   an explicitly-named number (`sync #99`) still works.

1b. **Pre-flight no-op classifier — skip trackers that obviously need no work.**
    Before spawning subagents, fetch lightweight state for every resolved tracker in one batched read,
    classify each as `dispatch` / `dispatch-urgent` / `skip-noop`, and dispatch only the non-skipped ones:
    one GraphQL round-trip instead of a ~50 KB subagent transcript per steady-state tracker (30–50% of a typical sweep).

    **One query, one round-trip.** Build one aliased GraphQL query covering every resolved issue.
    The `body` on `comments(last: 1)` separates skill-authored writes from human activity (see *Skill-or-bot detection* below).

    Write the query with the Write tool to `<scratch>/sync-preflight.graphql` (`<scratch>` is the session scratch directory, absolute),
    then run it as a plain `gh` command — a `$(…)` around `gh` keeps it sandboxed, where it cannot read its credentials:

    ```graphql
    query {
      repository(owner: "<owner>", name: "<repo>") {
        i<N1>: issue(number: <N1>) {
          number state closedAt updatedAt
          labels(first: 30) { nodes { name } }
          comments(last: 1) {
            nodes { author { login } createdAt body }
          }
        }
        i<N2>: issue(number: <N2>) { ... }
        # repeat one aliased block per resolved issue
      }
    }
    ```

    ```bash
    gh api graphql -F query=@<scratch>/sync-preflight.graphql
    ```

    **Skill-or-bot detection — required for the rules below.** The skill writes rollups and RM hand-offs as the operator's GitHub user, *not* a `*[bot]` account,
    so recognise its comments by the **marker** every status-rollup / hand-off / wrap-up comment begins with:

    ```text
    <!-- apache-magpie: <comment-kind> v<N> -->
    ```

    Treat the last-comment author as *bot-equivalent* if **any** of these holds:

    - `login in {github-actions[bot], dependabot[bot]}` or
      `login` ends with `[bot]` (real GitHub App accounts).
    - The body starts with `<!-- apache-magpie: ` (skill-authored
      comment — see [`tools/github/status-rollup.md`](../../../../tools/github/status-rollup.md)
      for the marker spec).
    - `login` matches a `bot_logins:` entry in the override file at
      [`.apache-magpie-overrides/security-issue-sync.md`](../../../../docs/setup/agentic-overrides.md)
      (for adopters with personal-account bots).

    The rules below call this composite check *"skill-or-bot"*.

    **Classification rule table.** Apply the rules **in order**; the first match wins.
    Conservative by design — `skip-noop` fires only when several signals align.

    | Signals | Decision | Reason recorded in recap |
    |---|---|---|
    | Last comment author is **not** skill-or-bot AND `createdAt` within last **24h** | `dispatch-urgent` | reporter just replied |
    | `updatedAt` within last **7 days** AND last comment is **NOT** skill-or-bot | `dispatch` | recent human activity — safety override |
    | Closed > **30 days** ago AND has `announced` label | `skip-noop` | `post-announce; CVE published` |
    | Closed > **90 days** ago AND no `announced` label | `skip-noop` | `stale closed (invalid/duplicate/abandoned)` |
    | Open AND has `cve allocated` + `pr merged` + `announced` AND last comment is skill-or-bot | `skip-noop` | `all phases done; awaiting closure heuristic` |
    | Open AND has `cve allocated` + `pr merged` AND last comment is skill-or-bot | `skip-noop` | `awaiting release` |
    | Open AND has `cve allocated` + `fix released` AND last comment is skill-or-bot | `skip-noop` | `fix released; awaiting advisory propagation` |
    | Anything else | `dispatch` | — |

    The skip rules need no *"idle > 14 days"*: once the labels show steady state and the last write was the skill's own,
    a recent `updatedAt` is not a reason to dispatch.

    **Hard rules**:

    - **Never silent; never skips a named tracker.** See [Hard rules for bulk mode](#hard-rules-for-bulk-mode):
      every skip is listed under *"Pre-flight skipped"* and can be `force-sync`ed,
      and explicit issue numbers (`sync #232, #233`) and CVE IDs (`sync CVE-2026-40913`) are never skipped — pre-flight skips only for set selectors (`sync all`, `sync announced`, label/title).
    - **Opt-out.** `--no-preflight` in the selector (e.g. `sync all --no-preflight`) bypasses the classifier and dispatches every resolved tracker —
      for trust-but-verify sweeps after a rule change.
    - **Dispatch-urgent is just dispatch.** It flags the tracker in the recap as *"recent reporter activity"*;
      the subagent it spawns is identical — the distinction is for the operator's attention.

    **What pre-flight does NOT do.** It does **not** decide *what action* a tracker needs — only whether a subagent is worth spawning.
    A `dispatch` tracker still runs the full Step 1 (gather) → Step 2 (proposal) flow in its subagent.

2. **Spawn one subagent per issue, in a single message.** Use the `general-purpose` subagent type
   and send every `Agent` call in the **same assistant message** so they run concurrently (20 surviving issues = 20 parallel calls in one turn).
   `skip-noop` trackers are **not** dispatched; they appear only under *"Pre-flight skipped"*.

   Each subagent prompt is self-contained and instructs the subagent to:

   - Do **only Step 1** (gather state) — no confirmations, edits, draft emails, label changes, milestone creation or comments.
     The subagent is a read-only assessor.
   - Read the issue, its closing-PR references, the fixing PR's state and milestone, and the originating Gmail thread,
     and mine comments and mail for the signals in the Step 1d table.
   - **Determine advisory-shipped state from the authoritative source, never the tracker body.**
     For any `cve allocated` tracker, search the public `<users-list>` archive for the CVE ID
     (PonyMail `search_list`, per [`tools/ponymail/`](../../../../tools/ponymail/); Gmail fallback)
     and cross-check cve.org publication state (per [`tools/cve-org/`](../../../../tools/cve-org/)).
     A `<users-list>` hit authored by the release manager **is** the advisory-shipped signal, and its `<mail-archive-url>/thread/<id>` permalink is the *Public advisory URL*.
     The body's *Public advisory URL* field and `announced` label are a **lagging mirror**, written only on the *next* sync after the out-of-band send:
     populated, they confirm shipment; empty is **never** proof the advisory did not ship.
     A `fix released` tracker with an empty *Public advisory URL* whose CVE is live on cve.org is a **Step 14→15 close-out**, not a parked tracker;
     report it via `advisory_shipped` / `advisory_url` (below) so it is not left stranded on its milestone.
   - Return a **compact structured report** in the shape below — not a freeform narrative.

3. **Bucket trackers by CVE-record impact.** Each proposed change falls into one of two buckets:

   - **CVE-affecting** — a change to a body field whose value lands in the regenerated CVE JSON pushed to Vulnogram:
     *Title* (the issue title, read verbatim into `containers.cna.title`), *Short public summary for publish*, *CWE*, *Severity*, *Affected versions*,
     *Reporter credited as*, *Remediation developer*, *PR with the fix*, *Public advisory URL*.
     These are the values that ship to `cve.org` and stay there — the same fields the [pre-push hygiene gates in Step 5b 1b](apply-and-push.md#decision-flow) scan.
   - **Non-CVE-affecting** — label flips, milestone touches, assignee swaps, project-board moves, status-rollup entries,
     reporter Gmail drafts, RM hand-off comments (template-bodied, no per-tracker CVE content).
     They change tracker state, not the published record.

   **The mechanical `allocated → review-ready` state push at
   `fix released` is NOT gated by the CVE-affecting bucket's
   per-item review**, which exists for *body-field content judgment* (summary wording, CWE choice, credit-line shape).
   The `allocated → review-ready` (Vulnogram: `DRAFT → REVIEW`) push that a `pr merged → fix released` transition mandates
   (the atomicity rule in [`apply-and-push.md` Step 5b](apply-and-push.md#step-5b--push-the-regenerated-json-to-the-cve-tool-via-the-adapter))
   rides the **same confirmation as the `fix released` label flip** in the non-CVE-affecting bucket and executes in the same apply pass.
   Do not hold a fix-released record at `allocated`/`DRAFT` for a separate CVE-affecting sign-off — that is the deferral the atomicity rule forbids.
   A body-field *content* change on the same tracker still goes through the CVE-affecting review; only the state push is exempt.

4. **Present buckets as merged bulk proposals; the
   CVE-affecting bucket gets a richer per-item view.** The
   proposal has three groups:

   - **Pre-flight skipped** *(if any)* — at the **top**, one line per `skip-noop` tracker with the rule that fired and the signals it saw,
     e.g. `#232 (closed 2025-12-04, announced label) — post-announce; CVE published`.
     **Informational** — nothing to confirm or apply; the user can `force-sync` any of them.
   - **Non-CVE-affecting bucket** — one combined proposal, confirmed once (`all`, `NN:all`, `NN:1,3`, per-issue subsets) and applied sequentially.
     Bundled because the actions are reversible, low-blast-radius, and stay off public CVE surfaces.
   - **CVE-affecting bucket** — **all CVE-record-affecting changes from all trackers as ONE merged bulk proposal**, one section per tracker showing:
     CVE ID, gate-failure summary, every body-field update with old / new value side by side, the planned regen+push action, any deferral conditions.
     The user reviews the **whole pack at once** with the same syntax (`all`, `NN:all`, `NN:1,3`, `NN:skip`, `NN:edit <item>: <new value>`),
     and the orchestrator applies the confirmed items across trackers sequentially.

   **Why bulk-review (and not per-tracker walk).** One merged proposal lets the operator compare summaries across trackers,
   spot two that should share a CWE, or three blocked on the same field, in one round-trip instead of N.
   The hygiene gates in [Step 5b 1b](apply-and-push.md#decision-flow) still catch *mechanical* drift on every regen;
   this surface is for *judgment* calls (threat-model framing, credit-line shape, CWE choice) before the push fires.

   **Confirmation syntax** for the merged proposal:

   - `all` — apply every proposed change across all trackers.
   - `<N>:all` — apply every change on tracker `<N>`; skip the others.
   - `<N>:1,3,5` — apply only the listed items on tracker `<N>`.
   - `<N>:skip` — skip tracker `<N>` entirely.
   - `<N>:edit <item-number>: <new value>` — replace the proposed item with a free-form override before applying.
   - `force-sync <N>` — dispatch a subagent for a `skip-noop` tracker:
     the full Step 1 gather runs on the next turn and its result folds into the next proposal.
   - `cancel` / `none` — apply nothing.

   **Proposal order in the merged pack.** Trackers appear in **ascending tracker-number order**, stable across reruns.
   The operator can name a different order at confirmation (*"apply #438 first; I want to think about #232 last"*) and the orchestrator honours it.

5. **Apply sequentially, not in parallel.** Assessment ran in parallel, but the apply phase is sequential
   so `gh` rate limits, partial failures and user interrupts stay legible.
   Do not spawn subagents for the apply phase.

### Subagent report shape

Each subagent returns a single code block (or JSON) with exactly these fields, so the orchestrator merges deterministically:

```yaml
issue: <N>
title: <one line>
scope_label: <scope-a> | <scope-b> | <scope-c> | <missing>
current_labels: [<label>, ...]
current_milestone: <title or null>
current_assignees: [<login>, ...]
fix_pr:
  url: <<upstream> PR URL or null>
  state: open | merged | closed | null
  author: <login or null>
  author_is_security_team: true | false | null
  merged_at: <ISO8601 or null>
  milestone: <PR milestone title or null>
release_shipped: true | false | unknown
advisory_shipped: true | false | unknown   # from the <users-list> archive search for the CVE ID — NOT derived from the tracker body
advisory_url: <<mail-archive-url>/thread/... permalink, or null>   # the archive permalink when advisory_shipped is true
cve_published: true | false | unknown      # cve.org publication state (MITRE API), independent of the tracker body
reporter:
  name: <name or null>
  email: <email or null>
  gmail_thread_id: <id or null>
  credit_confirmed_as: <string or null>
  credit_question_pending: true | false
cve_id: <CVE-YYYY-NNNNN or null>
process_step: <number from the README table>
proposed_label_add: [<label>, ...]
proposed_label_remove: [<label>, ...]
proposed_milestone: <title or null, with note "(create)" if it does not yet exist>
proposed_assignees_add: [<login>, ...]
proposed_body_field_updates: [<one-line description>, ...]
proposed_status_comment: <one-line summary or null>
proposed_reporter_email: <one-line summary or null>
blockers: [<short reason the orchestrator or user must resolve before apply>, ...]
notes: <free-form one-to-three sentences, only if something does not fit above>
```

The orchestrator builds the merged proposal table from these fields and uses `blockers` to flag what needs user input (e.g. a missing Gmail thread or an ambiguous credit line).
When `advisory_shipped` (or `cve_published`) is true on a tracker still labelled `fix released`,
bucket it into the Step 14→15 close-out **regardless** of an empty *Public advisory URL* body field — the archive/cve.org signal is authoritative; the empty field is sync lag.

### Hard rules for bulk mode

- **No mutations in subagents.** Subagents must not call `gh issue edit`, `gh issue comment`, `gh api … -X PATCH/POST`, `gh label create`,
  `gh api …/milestones` (create), or any Gmail send / draft-create tool.
  If a subagent reports a mutation, surface it as a bug and stop.
- **No new CVE allocations in subagents.** Printing the CVE allocation URL is fine; allocating is a human step.
- **Gmail drafts are created by the orchestrator**, only after user confirmation, from its main context.
- **Confidentiality still applies** to subagents: no `<tracker>` content leaks into any public surface.
- **Link-form self-check still applies** to the merged output — every `#NNN` is a clickable link per Golden rule 2.
- **Pre-flight skips are never silent.** Every Step 1b `skip-noop` appears in the *"Pre-flight skipped"* group with the rule that fired;
  the user can `force-sync <N>` any of them, and `--no-preflight` bypasses Step 1b entirely.
- **Pre-flight never skips an explicitly-named tracker.** For named numbers (`sync #232, #233`) and the trackers a CVE ID resolves to (`sync CVE-2026-40913`) Step 1b runs the classifier only for context
  (so the recap can say *"#232 looks idle — sync anyway?"*) and never skips.
  Skip-eligible selectors are state/label/title selectors like `sync all` or `sync announced`.

### When bulk mode is **not** appropriate

- The user asked for a single issue (`sync #216`). Run the normal flow in the main agent.
- The user wants to *drive* the sync interactively ("walk me through #216, I want to review each signal as we go") — bulk mode collapses the per-issue detail; use single-issue mode.
- The action needs a deep multi-turn conversation (e.g. "help me decide whether this is even valid") — use single-issue mode.

---
