<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — existing-tracker dedup

## Step 2 — Deduplicate against existing <tracker> issues

For each candidate `threadId`, check the authoritative *Security mailing list
thread* field of existing tracker issues. Do **not** use GitHub issue-body
search as proof that a thread is untracked: search indexing can miss opaque
identifiers enclosed in Markdown backticks.

Write all candidate IDs to `<scratch>/thread-ids.json`. Use the configured
vetted-ops policy and its `security-issue-import` caller to read the complete
bounded GitHub tracker index:

```bash
vetted-op-read --caller security-issue-import \
  --save security-import-index.json issue-list-with-bodies
```

The operation reads up to 1000 issues, including open and closed issues.
It must be explicitly authorized in the adopter's vetted-ops `[callers]`
policy. Never bypass a missing grant with direct `gh` calls; ask the user to
approve the minimal caller-policy change instead. The `--save` target must
be a pre-existing, marked, owner-controlled directory, as documented in
`tools/vetted-ops/README.md`. Do not print saved issue bodies into model
context. Reuse the saved index for this import run, including Step 2b.

Run the deterministic matcher against the saved JSON file:

```bash
<sm> dedup-index \
  --thread-ids <scratch>/thread-ids.json \
  --issues <saved-index-path>
```

If the adopting project customizes tracker body headings, also pass
`--body-fields <scratch>/body-fields.json`, using the configured role-to-heading
mapping. The matcher extracts the authoritative `mailing_thread` field and
compares exact normalized thread identifiers. It returns only matching issue
summaries, never full issue bodies.

**Exit 2** for unsupported identifiers or invalid inputs means stop and
surface the refusal. If `complete` is false, or any field is `undecided`,
do not classify unmatched threads as new; ask for a manual resolution.
A full 1000-issue index is potentially truncated and cannot support
negative deduplication claims. On Jira or local-files trackers, the
body-index operation is currently unsupported: stop and request a
backend-supported check rather than assuming no matches.

Any ID in `tracked` has already been imported — skip it and link the existing
issue. If an explicitly requested thread is already tracked, tell the user.
Only IDs in `untracked` may proceed to the on-thread check below.

**Budget guardrail:** fetch one bounded tracker index per import run; never
re-fetch the index for every candidate. If no candidates remain, stop without
reading email bodies.

### 2-bis. Drop threads already answered on-thread without a tracker

Between the two tracker-level dedup filters (`2` exact-threadId and `2a` fuzzy-duplicate) sits a thread-level filter for
**reports that the security team has already canned-responded to on the mailing-list thread itself, without ever creating a tracker**
(the disposition was obvious on read — classic out-of-scope DoS-by-authenticated-users,
Simple-Auth-Manager scope-miss, Dag-author user-input class, or similar).
These threads are *done*; re-surfacing them makes the triager re-read reports already answered.

Detection shape — for each candidate that survived Step 2, run a
single `mcp__claude_ai_Gmail__get_thread` with
`messageFormat: MINIMAL` (cheap — headers + snippet only) and
check:

1. **At least one message in the thread is authored by a
   security-team member.** Cross-reference the `From:` of each
   non-root message against the collaborator list of
   `<tracker>` fetched once in Step 0 (authoritative: `gh api
   repos/<tracker>/collaborators --jq '.[].login'`; do not
   re-fetch it per candidate) or
   the roster declared in
   [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md).
   A message from a team member on an inbound report thread is
   almost always a canned-response reply.

2. **The snippet of that team-member reply looks like a canned
   disposition.** Matches against any of these shapes (case-
   insensitive, on the first ~300 chars of the snippet):

   - *"Thank you for the report. We cannot accept it"* / *"We
     cannot review it"* / *"We do not consider this a
     vulnerability"* / *"We do not consider this a security
     issue"*
   - *"Per the project's security model"* / *"documented in our
     Security Model"* / *"this is by design"* / *"this is
     expected behaviour"*
   - *"This is explicitly out of scope"* / *"is explicitly
     out-of-scope"*
   - *"please submit it via the regular contribution process"* /
     *"welcome a PR through the regular contribution process"*
   - *"accounts that repeatedly send reports which do not meet
     the policy"* (the deny-list warning — always canned)
   - A verbatim opening line from one of the canned responses in
     [`canned-responses.md`](../../../../<project-config>/canned-responses.md).

   Only confirm a match when the reply is *structurally* a canned response.
   A team member asking the reporter a clarifying technical question does **not** fit this filter;
   that is a live triage discussion and the thread deserves a tracker.

3. **The reporter's trail after the team reply is either accepting
   or silent.** Three acceptable terminal states:

   - No reporter message after the team reply at all.
   - A short acknowledgement (*"thanks"*, *"understood"*,
     *"I'll follow the contribution process"*, an emoji
     reaction, a "reacted to your message" Gmail meta-message).
   - A reporter pushback that the team already answered a second
     time with a follow-up canned paragraph (two team replies,
     no further reporter message). A thread with the reporter
     pushing back and **no** team follow-up is **not** silent —
     that is open correspondence and belongs as a tracker.

   Measure silence from the most recent reporter message:
   **≥7 days of silence after a canned reply** is enough to treat the thread as closed.
   A reporter who replies at day 8 re-surfaces the thread via the `newer_than:14d` window, so the closure is not permanent.

When 1 + 2 + 3 all hold, classify the candidate as
`already-responded-no-tracker` and **drop it silently** — do not
import, do not re-draft the canned response, do not surface to the
user as a candidate in Step 5. Record a one-line entry in the
recap's `dropped` section so the user knows the filter fired:

> Dropped `19d2f402867e957e` *(already answered on-thread
> 2026-03-28 by `<security-team-member>` with the
> DoS-by-authenticated-users canned response; reporter silent
> since)*.

**When to stay cautious.** If the team reply does not match a canned-response shape cleanly
— e.g. a free-form assessment that looks substantive — **do not drop**.
Send the thread through to Step 3; the user may want a tracker to record the team's assessment formally.

**Budget guardrail**: one MINIMAL `get_thread` call per candidate (on top of the batched Step 2 search).
Do not use FULL_CONTENT here — the snippet + `From:` headers classify the shape,
and the one FULL_CONTENT fetch per surviving thread happens in Step 2a.
If the snippet is ambiguous (the canned-response opening is cut off), default to *keep the candidate*.

**Hard rule**: this filter drops threads **that have a team reply and no tracker**.
It never drops a thread that has a tracker (Step 2's job)
and never drops a thread that has only the reporter's messages (a new, unanswered report).

---
