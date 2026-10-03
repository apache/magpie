<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — existing-tracker dedup

## Step 2 — Deduplicate against existing <tracker> issues

For each candidate `threadId`, check whether that ID already appears in an `<tracker>` issue body
(the *"Security mailing list thread"* field holds it, as a `<mail-archive-url>/thread/<id>` URL or a textual note containing the Gmail `threadId`).
Check every candidate in one pass: OR the `threadId`s into one `gh search issues` query,
at most 6 IDs per query (GitHub search allows at most five `OR` operators):

```bash
gh search issues "<threadId-1> OR <threadId-2> OR … OR <threadId-6>" \
  --repo <tracker> --match body --limit 100 \
  --json number,title,state,url,body
```

Attribute each hit to a candidate by finding which `threadId` its
`body` contains; a hit can match more than one candidate.
If a query returns exactly 100 hits, the result may be truncated —
split that batch into smaller ones and re-run rather than treating
the unmatched `threadId`s as untracked.

If the search returns any hit for a candidate, the thread is already imported — skip it; do **not** propose re-importing.
If the user explicitly passed `import thread:<id>` and the thread is already imported, tell the user and link the existing issue.

The remaining candidates proceed to the on-thread-handling check below;
only threads that survive both filters reach the user in Step 5.

**Budget guardrail**: if the de-dup step knocks the candidate set down to zero, say so and stop, without reading any email bodies.

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
