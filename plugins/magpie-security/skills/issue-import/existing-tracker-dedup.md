<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — existing-tracker dedup

## Step 2 — Deduplicate against existing <tracker> issues

For each candidate `threadId`, check whether that ID already appears in
an `<tracker>` issue body. The sync skill records each thread
ID in the *"Security mailing list thread"* field of the tracking issue
(either as the `<mail-archive-url>/thread/<id>` URL or as a textual note
containing the Gmail `threadId`). One `gh search issues` call is
enough:

```bash
gh search issues "<threadId>" --repo <tracker> --match body --limit 5 \
  --json number,title,state,url
```

If the search returns any hit, the thread is already imported — skip
it. Do **not** propose re-importing (that would create a duplicate
tracker). If the user explicitly passed `import thread:<id>` and the
thread is already imported, tell the user and link the existing issue
rather than trying to create a duplicate.

After de-duplication, the remaining candidates proceed to the
on-thread-handling check below. Only threads that survive both
filters reach the user in Step 5.

**Budget guardrail**: if the de-dup step knocks the candidate set down
to zero, say so and stop. Do not read any email bodies, do not burn
Gmail quota on threads that have no work to do.

### 2-bis. Drop threads already answered on-thread without a tracker

Between the two tracker-level dedup filters (`2` exact-threadId and
`2a` fuzzy-duplicate) sits a thread-level filter that catches a
third class of non-candidates: **reports that the security team has
already canned-responded to on the mailing-list thread itself,
without ever creating a tracker** (because the disposition was
obvious on read — classic out-of-scope DoS-by-authenticated-users,
Simple-Auth-Manager scope-miss, Dag-author user-input class, or
similar). These threads are *done*; surfacing them again as
"import candidate" would force the triager to re-eyeball the same
reports they already answered days or weeks ago. That is exactly
the noise the shorter `import new` window was tightened for, and
this filter is its natural companion.

Detection shape — for each candidate that survived Step 2, run a
single `mcp__claude_ai_Gmail__get_thread` with
`messageFormat: MINIMAL` (cheap — headers + snippet only) and
check:

1. **At least one message in the thread is authored by a
   security-team member.** Cross-reference the `From:` of each
   non-root message against the collaborator list of
   `<tracker>` (authoritative: `gh api
   repos/<tracker>/collaborators --jq '.[].login'`) or
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

   Only confirm a match when the reply is *structurally* a canned
   response — not every team-member reply is. A team member
   asking the reporter a clarifying technical question does
   **not** fit this filter; that is a live triage discussion and
   the thread deserves a tracker.

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

   Use the date of the most recent reporter message to measure
   silence: **≥7 days of silence after a canned reply** is
   enough to treat the thread as closed. A reporter who replies
   at day 8 will re-surface the thread via the `newer_than:14d`
   window anyway, so the closure is not permanent.

When 1 + 2 + 3 all hold, classify the candidate as
`already-responded-no-tracker` and **drop it silently** — do not
import, do not re-draft the canned response, do not surface to the
user as a candidate in Step 5. Record a one-line entry in the
recap's `dropped` section so the user knows the filter fired:

> Dropped `19d2f402867e957e` *(already answered on-thread
> 2026-03-28 by `<security-team-member>` with the
> DoS-by-authenticated-users canned response; reporter silent
> since)*.

**When to stay cautious.** If the team reply does not match a
canned-response shape cleanly — e.g. the team member wrote a
free-form assessment that looks substantive — **do not drop**.
Send the thread through to Step 3 for normal classification; the
user may want to import it as a tracker after all (for example, to
record the team's assessment formally rather than rely on the
mail-thread paper trail).

**Budget guardrail**: one MINIMAL `get_thread` call per candidate
(on top of the Step 2 search). This step deliberately avoids
FULL_CONTENT — the snippet + `From:` headers are enough to
classify the shape. If the snippet is ambiguous (the canned-
response opening is cut off), default to *keep the candidate*
rather than risk a false-positive drop.

**Hard rule**: this filter drops threads **that have a team reply
and no tracker**. It never drops a thread that has a tracker (that
is Step 2's job) and never drops a thread that has only the
reporter's messages (that is a new, unanswered report — the whole
point of the skill).

---
