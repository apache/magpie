<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — reject screening and proposal

## Step 2b — Search Gmail for prior rejections of similar reports

Step 2a finds existing *trackers* that overlap with the candidate.
Step 2b finds **prior reports we rejected without creating a tracker**:
a reporter sent a nearly-identical claim weeks ago, the team replied with a canned response from
[`canned-responses.md`](../../../../<project-config>/canned-responses.md), and the thread ended there.
That precedent matters when the candidate is heading for a negative-response disposition
(`skip`, `reject-with-canned`, or a pending `automated-scanner` / `consolidated-multi-issue` / `media-request` class):
reusing the same canned response keeps the team's answer consistent across reporters.

**Run Step 2b on** every candidate that Step 3 is likely to classify as a non-tracker disposition,
AND on any `Report` or forwarder-relayed candidate where the Step 2a fuzzy match is WEAK/MEDIUM-only
and the body reads like a well-known negative pattern
(a Security-Model-fit claim, a Dag-author-supplied-input premise,
a "you should restrict environment-variable access from Dags" suggestion,
an unauthenticated-DoS-via-rate-limit request, an image-scan dump).
Skip Step 2b on candidates Step 2a flagged STRONG (those route to dedupe, not rejection)
and on `cve-tool-bookkeeping` (dropped silently).

**Closed-invalid tracker cross-check — run on EVERY surviving candidate,
unconditionally.** Unlike the conditional mail search, this check runs on **every** `Report` / forwarder-relayed candidate that survived Step 2:
a near-twin of a tracker the team already closed as invalid (same component / bug-class) is the strongest "we normally reject this" signal,
and catching it here lets the Step 5 proposal say *"matches #NNN, closed invalid"* up front.
Reuse the Step 2a component / code-pointer / subject-keyword tokens
(and the cleaned keywords file Step 2a's injection guard wrote, single-quoted in a plain `gh` call)
and search closed trackers carrying the project's closing-disposition labels
(the `invalid` / not-CVE-worthy / `duplicate` label names declared in
[`<project-config>/scope-labels.md`](../../../../<project-config>/scope-labels.md) → *Closing dispositions*):

```bash
gh issue list --repo <tracker> --state closed \
  --label "<invalid-label>" --search '<cleaned keywords>' --limit 10 \
  --json number,title,closedAt,url
```

A hit whose title / component matches the candidate is a **reject-class precedent**:
open its closing comment to confirm the disposition reason, map that reason to its canned response,
and surface it in the Step 5 proposal as `reject-with-canned <name>` with the precedent linked
(`matches [#NNN](...), closed invalid — <one-line reason>`).
Budget: **≤ 3 `gh` calls**.
**Confidence discipline**: a precedent only loosely related (same component, different bug class)
is surfaced as *"related: #NNN"* context, **not** an automatic reject.
The tracker scan answers "we already rejected a near-twin of this as a *tracker*";
the mail search answers "we already answered this *on-thread* without ever opening a tracker".

**Search recipe — two Gmail calls per candidate, maximum.** The
query templates and the substitution-values guide live in
[`tools/gmail/search-queries.md`](../../../../tools/gmail/search-queries.md#security-issue-import--prior-rejection-search);
in short:

**Backend selection.** When PonyMail MCP is enabled and authenticated (Step 0)
**and** `<security-list>` is in `.apache-magpie-overrides/user.md` → `tools.ponymail.private_lists`,
**PonyMail MCP is the primary backend for this step**:

```text
mcp__ponymail__search_list(
  list: "security",
  domain: "<project>.apache.org",
  query: "<keyword-1> <keyword-2>",
  timespan: "lte=24M"
)
```

The two-year lookback is the default because precedent-shape reports recur over a long window.
Gmail is the fallback when (a) PonyMail is not enabled / not authenticated,
(b) the private list is not in the allowlist,
or (c) the PonyMail query comes back empty and you want a last check against the user's mailbox.
The per-candidate budget is ≤ 2 archive searches (whichever backend) for the prior-rejection path.

1. **Prior rejections by the security team.** Pick 2–3 distinctive noun phrases from the report
   (reuse the Step 2a subject-keyword tokens) and search the security list for past outbound replies from team members.
   Canonical `mcp__claude_ai_Gmail__search_threads` query shape — substitute the project's `<security-list-domain>` from
   [`<project-config>/project.md`](../../../../<project-config>/project.md#gmail-and-ponymail):

   ```text
   list:<security-list-domain> "<keyword-1>" "<keyword-2>"
   newer_than:180d -from:notifications@github.com -from:noreply@github.com
   ```

   Hits whose author is on the security-team roster AND whose body opens with a canned-response cue
   (*"Thank you for reporting … this isn't a security issue"*, *"Per the project's security model"*,
   *"This is documented / expected behaviour"*, etc.) are prior rejections.
   Fetch each with `mcp__claude_ai_Gmail__get_thread`:
   MINIMAL confirms the canned-response shape;
   use FULL_CONTENT only when the reporter pushed back and you need the team's clarification.

2. **Inbound reports that never became a tracker.** Same keywords,
   same 180-day window, filtered to **inbound** messages:

   ```text
   list:<security-list-domain> "<keyword-1>" "<keyword-2>"
   newer_than:180d -from:me -from:<security-team-member>
   -from:notifications@github.com -from:noreply@github.com
   ```

   Cross-reference the hits' `threadId`s against existing trackers in one batched query, as in Step 2 —
   `gh search issues "<threadId-1> OR … OR <threadId-6>" --repo <tracker> --match body --limit 100 --json number,body`
   (≤ 6 IDs per query), attributing each hit to the `threadId` its body contains
   (the *Security mailing list thread* field or the rollup's threadId backfill note).
   The hits with **no** corresponding tracker are the "rejected without tracker" precedents.

**Surfacing in Step 5.** For each precedent found, attach to the
candidate's proposal entry:

- a clickable link to the prior thread (Gmail or PonyMail URL);
- the canned-response **name** the team used (exact section heading in
  [`canned-responses.md`](../../../../<project-config>/canned-responses.md),
  e.g. *"When someone claims Dag author-provided 'user input' is dangerous"*) — if identifiable;
- a one-line summary of the reporter's follow-up: *"accepted — thread closed"*,
  *"pushed back on X; team clarified Y"*, *"no reply after our response"*;
- a recommendation — *"use the same canned response verbatim"*,
  *"use the same canned response with an inline augmentation pre-empting X (the ambiguity the prior reporter stumbled on)"*,
  or *"treat as new ground — no suitable precedent found"*.

Absence of precedent is information too:
record *"no prior rejection of a similar report in the last 180 days"* explicitly, so the user knows Step 2b ran.
The Step 5 canned-response discipline still applies.

**Budget guardrail for Step 2b**: **≤ 2 Gmail calls per candidate**.
Do not iterate deeper; if the two searches return nothing relevant, record *"no precedent"* and move on.

**Hard rule**: Step 2b is a **read-only** signal-gathering pass.
Do not draft, and do not quote the prior reply back to the reporter before the user confirms the canned response in Step 5.
The precedent informs *which* canned response to propose and *whether* to augment;
the drafting happens in Step 7 from the canned-responses file, not by pasting prior outbound mail.

---

## Step 4a — Preliminary reject-class triage

**Run this on EVERY surviving candidate, mandatorily — including
candidates that read as clean `Report`s headed for default-import.**
[`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md) documents the "we already know these are not vulnerabilities" patterns:
the out-of-scope shapes the Security Model carves out.
Importing a *plain* instance as `Needs triage` and closing it days later wastes triage capacity,
so this step catches the plainly-clear cases and lets the Step 5 proposal recommend the canned rejection instead;
the default-to-import bias (Golden rule 1) still governs everything ambiguous.

**The check is the project's reject-pattern taxonomy, not a fixed
list.** Read the *reject-pattern taxonomy* declared in
[`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md)
(each canned-response heading is one pattern, with its "when it applies" trust-boundary / Security-Model anchor).
Compare each surviving candidate's full extracted body against it
and emit exactly one of three outcomes, **always reported in the Step 5 proposal**:

- **`reject-with-canned <pattern>`** — the report *plainly* fits one taxonomy pattern
  (or a [Step 2b](#step-2b--search-gmail-for-prior-rejections-of-similar-reports) closed-invalid / prior-rejection precedent hit).
  The proposal line names the canned-response pattern verbatim,
  quotes the 1–2 sentences of the report that fit it,
  and cites the trust-boundary / Security-Model anchor the rejection rests on.
- **`hold-for-human-review`** — borderline: the reporter explicitly claims a path that *could* escape the carve-out
  (e.g. a non-Dag-author / unauthenticated route to a sink the taxonomy normally treats as trusted-input-only),
  or the body could not be fully retrieved.
  Surface the ambiguity; make no default recommendation; the user decides in Step 6.
- **explicit no-match** — a one-line *"reject-class check: no match
  against the canned-response taxonomy or the Step 2b
  closed-invalid / prior-rejection precedents"*.

**Never skip the check to save time, and never present a candidate as
a plain default-import without having run it.** A silent skip costs the user a round-trip
(*"is this one we normally reject?"*) the check exists to pre-empt.

**Confidence discipline.** Flag `reject-with-canned` **only when the report plainly fits** the pattern;
everything borderline routes to `hold-for-human-review`, never to a default reject
(*"wrongly-rejected is worse than wrongly-imported"*, Golden rule 1).

**On user confirm.** A confirmed `reject-with-canned` candidate follows the `NN:reject-with-canned <name>` path
(Step 5 / Step 6 / Golden rule *rejection means no tracker, ever*):
**no tracker is created**, and a Gmail draft using the named canned response is queued on the originating thread.
A confirmed `hold-for-human-review` candidate falls back to whatever the user picks (import / skip / reject-with-canned) in Step 6.

The taxonomy match here is *"this shape is out of scope by the Security Model"*;
the [Step 2b](#step-2b--search-gmail-for-prior-rejections-of-similar-reports) scan is *"we already rejected this exact thing"*.
Apply both on every candidate.

---

## Step 5 — Propose the imports

Present all candidates as a single numbered proposal grouped by class:

- **Reports defaulting to import** (class `Report`, or a forwarder-relayed candidate classified by the optional [`security-issue-import-via-forwarder`](../issue-import-via-forwarder/SKILL.md) sub-skill):
  for each, show the proposed title, the extracted body (with `_No response_` placeholders visible),
  the receipt-of-confirmation reply preview, and a one-line
  *"unless you say otherwise, this lands as a new tracker in `Needs triage` with the receipt-of-confirmation reply drafted to the reporter"*.
  Surface inline any Step 2a fuzzy-duplicate matches (`STRONG`/`MEDIUM`/`WEAK`),
  the [Step 4a](#step-4a--preliminary-reject-class-triage) reject-class verdict
  (`reject-with-canned <pattern>` / `hold-for-human-review` / explicit no-match),
  and any classification ambiguity, so the user can scan-then-override;
  do **not** pose them as open questions that gate the import.
  A `reject-with-canned` verdict flips this candidate's recommended default from import to the canned rejection (still overridable in Step 6).
- **Candidates not to import** (class `automated-scanner`, `consolidated-multi-issue`, `media-request`, `spam`,
  `cross-thread-followup`, `fix-already-public`): show the class, the reporter, a one-line summary,
  and the proposed Gmail draft (from `canned-responses.md`, or — for `fix-already-public` — from the *fix-already-public reply shape* below)
  or the proposed follow-up action
  (e.g. *"comment on existing tracker [<tracker>#NNN](https://github.com/<tracker>/issues/<N>)"*).
  These need explicit confirmation — no default-to-tracker.
  The draft **must** follow the canned-response discipline below.
- **Dropped silently** (class `cve-tool-bookkeeping`): do not surface these;
  `security-issue-sync` Step 1e consumes them.
  Report only the count in the recap (*"N CVE-tool-bookkeeping emails dropped"*).
  This holds whether Step 3 or the
  [Step 1 pre-filter](candidate-listing.md#step-1-pre-filter--classes-decidable-from-subject-and-sender)
  classified the thread.
- **Pre-filtered at Step 1** (class `cve-tool-bookkeeping`): end
  the proposal with one informational line giving the count —
  *"Pre-filtered at Step 1 by subject/sender: N
  cve-tool-bookkeeping — listed in the recap; `keep <threadId>`
  sends one through Steps 2–3"*. It asks for no decision; omit it
  when the count is zero.

### fix-already-public reply shape

For each `fix-already-public` candidate, propose this draft (fill
in the placeholders from the Step 2c match):

> Thank you for taking the time to report this through
> `<security-list>`. We noticed that
> [`<upstream>#<NNN>`](https://github.com/<upstream>/pull/NNN)
> ([`<author>`](https://github.com/<author>), <merged/opened> on
> YYYY-MM-DD) already appears to address what you described.
>
> Per our policy, we do not add a finder when the fix to the
> reported issue is already public at the time of report — but
> we very much appreciate your effort in writing to us, and the
> care you took to send it via the private channel.
>
> Could you check whether
> [`<upstream>#<NNN>`](https://github.com/<upstream>/pull/NNN)
> fixes the behaviour you observed? If it does, no further action
> is needed on your side. **If after testing with this PR you
> still see the issue, please reply on this thread with the
> failing reproduction** and we will reopen the assessment as a
> regular report.

Substitute *"opened on"* when the PR is not yet merged.
If Step 2c surfaced multiple candidate PRs and the user has not narrowed to one,
list each PR on its own line and ask the user to pick (or keep all if each covers a different aspect of the report).

This reply is the **disposition** for `fix-already-public` candidates — no tracker is created, no internal ticket opened.
The audit trail is the `<security-list>` thread (the report + this reply).
If the reporter pushes back that the PR does not fix it,
their reply resurfaces in the next run and the candidate is re-classified as a regular `Report`.

**Reporter credit field.** The policy from
[`security-issue-import-from-pr`](../issue-import-from-pr/SKILL.md#reporter-credit-policy-for-public-pr-imports)
applies symmetrically: no finder credit for a report that arrived after the fix went public.
The user can override in Step 6 for a project-specific reason
(e.g. the reporter privately spotted the issue before the unrelated PR landed).

### Consolidated receipts for multi-tracker imports

When the resolved selector imports **N > 1 trackers from the same
reporter or same source thread within one skill run**, propose a
**single consolidated receipt-of-confirmation reply** that lists
all N tracker URLs, instead of N separate receipts.

**Detection conditions** (any one is sufficient):

1. All N trackers reference the same Gmail `threadId` in their
   "Split from" / "Imported from" provenance (e.g. one reporter
   split a consolidated report into N separate GHSAs).
2. All N trackers' inbound `From:` addresses are identical
   (same reporter sent N independent reports in the same run).
3. All N trackers were imported from N distinct threads that
   *share an outer thread* (one reporter, one root, N
   sub-threads).

**Consolidated receipt shape**:

- Reply on the **earliest** thread in the set (where the team
  has an established channel with the reporter — typically the
  consolidated-pre-split thread).
- List each tracker URL + GHSA ID / equivalent identifier on
  its own line, one per tracker.
- Ask the credit-preference question **once**, applying to all
  trackers in the set.
- Use the *"Confirmation of receiving the report"* canned body
  with a leading paragraph that lists the trackers.

**Skip the per-tracker receipt drafts** when the consolidated one is created.
Surface the consolidated draft with explicit *"this reply covers trackers #N1, #N2, …"* framing so the user knows what's bundled.

**Coherence check**: the consolidated reply must accurately characterise *each* tracker, not just the largest one.
If the reports differ so much that one reply would confuse, fall back to per-tracker receipts; do not force the bundle.

### Canned-response discipline for negative-response drafts

When the proposed disposition is a negative response — any of the
`NN:reject-with-canned`, `automated-scanner`, `consolidated-multi-issue`, `media-request`, `cross-thread-followup` paths —
**strongly prefer the canned response verbatim** over fresh prose.
The library in [`canned-responses.md`](../../../../<project-config>/canned-responses.md) is wording the team has iterated on;
a fresh draft that says "roughly the same thing" re-introduces ambiguities the canned version already ironed out.

**Pick the single canned response that best matches** the candidate's shape.
Name it in the proposal by its exact section heading in `canned-responses.md`
(e.g. *"When someone claims Dag author-provided 'user input' is dangerous"*).
When Step 2b surfaced a precedent, the canned response the team used last time is the strong default;
deviate only for a specific, defensible reason.

**Use the canned body verbatim** except for the SCREAMING_SNAKE_CASE placeholders (reporter name, CVE ID, PR URL, etc.).
Do not paraphrase, reorder or "polish" it;
wording changes belong in `canned-responses.md` via a separate commit, not in a one-off draft.

**Add an inline augmentation only when** the canned response has a
specific ambiguity in the context of *this* report that a typical
reader would plausibly misread — for example:

- the canned response assumes the reporter's claim is X but the report actually claims X' (a stricter variant);
  the augmentation clarifies which variant the reply addresses;
- the reporter pre-empted the standard Security Model argument by citing a specific sentence from the model;
  the augmentation quotes that sentence and explains why the canned response still applies;
- the Step 2b precedent showed a prior reporter pushing back on ambiguity Y, and the current report carries Y too;
  the augmentation pre-empts Y.

**Clearly mark the augmentation** as a distinct inline block the reviewer can strip cleanly:
insert a `> **[Inline addition for this report]** <augmentation text>` block at the point where the canned wording is ambiguous,
leaving the surrounding canned text untouched.
The reviewer must see at a glance which sentences are canned,
and be able to delete the augmentation without leaving a grammatical orphan.

**Coherence check before presenting the draft.** Re-read the proposed reply as the reporter would, with the report beside it.
Verify:

- the draft accurately characterises **this** report — e.g. do not claim "this requires Dag-author privileges"
  when the reporter described an unauthenticated attack;
  do not say "the behaviour is documented here" when the linked docs describe a different scenario;
  do not cite a Security Model chapter that does not cover the reporter's claim;
- the canned body and the augmentation (if any) do not contradict each other —
  a canned "we will not be issuing a CVE" paragraph next to an augmentation saying "we plan to publish an advisory" is the failure mode;
- the tone stays polite-but-firm (see AGENTS.md) throughout; augmentations must not drift into hedging or apology;
- every placeholder has been filled in (no literal `CVE_ID`/`PR_URL`/`REPORTER_NAME` tokens left behind);
- every artefact URL the draft cites exists and says what the draft claims — a dead link or a misrepresented doc is worse than no link.

If the coherence check surfaces **any** contradiction, mismatch, or shaky claim, fix it before surfacing the draft in the proposal.

Confirmation forms (`Report` and forwarder-relayed candidates default
to import; the user only types back to *deviate* from that default):

- `all` / `go` / `proceed` / `yes, all` / no reply at all — import
  every Report and forwarder-relayed candidate as proposed (each
  lands in `Needs triage` with its receipt-of-confirmation reply
  drafted), and apply every confirmed non-import action.
- `skip NN` — reject candidate `NN` upfront; no tracker created, no
  draft. Combine with `, ` to skip multiple (`skip 1, 3`).
- `NN:reject-with-canned <canned-response-name>` — reject candidate `NN` upfront *and* draft the named canned reply
  (typically a negative-assessment template like *"parameter-injection-to-operator-or-hook"*,
  *"dag-author-user-input-claims"*, or an *"obvious-duplicate-of-recently-closed-tracker"* note).
  **No tracker is created** (Golden rule *rejection means no tracker, ever*).
  Use this when the team has decided pre-triage that the report does not warrant a tracker
  (Security-Model-fit miss, Dag-author-input pattern, recently-closed duplicate, etc.).
- `NN:reject-with-public-fix <PR-URL>` — reject candidate `NN` upfront with the *fix-already-public reply shape* (see above),
  citing `<PR-URL>` as the public PR.
  Use this when Step 2c missed an existing PR the user knows about,
  or to upgrade a MEDIUM Step 2c match to a STRONG `fix-already-public` disposition.
  **No tracker is created**; no finder credit is recorded per the policy.
  Supply multiple comma-separated `<PR-URL>` values if more than one PR collectively covers the report.
- `NN:edit <freeform>` — fold a freeform note (extra context, a
  different title, a smaller body excerpt) into the import; tracker
  is still created with the edits applied.
- `none` / `cancel` — bail entirely; no trackers, no drafts.

**There is deliberately no "create the tracker so the team can close
it as invalid later" path.** If the team has decided pre-triage that the report is invalid,
use `skip NN` (silent) or `NN:reject-with-canned <name>` (with a courtesy reply);
see Golden rule *rejection means no tracker, ever*.

---
