<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-triage — classification

## Step 3 — Classify

### Class-by-class decision criteria

#### `VALID`

Propose when **all** of:

- The reported behaviour, as described, violates a documented
  rule in the project's Security Model (cited by URL in the
  proposal body — see
  [`<project-config>/security-model.md`](../../../../<project-config>/security-model.md)
  for the per-project pointer).
- The attack vector is reachable by an attacker who does **not**
  already have an authoritative role (operator, host
  administrator, DAG author when DAG-author-trust is documented
  out of scope).
- The fix shape is implementable in `<upstream>` without
  cross-team coordination (or, if cross-team work is needed,
  the team has consensus on the approach — usually a sibling
  vector has already been fixed and this is the next branch).
- No load-bearing open question about whether the report's
  premise is even correct (technical claims have been verified
  against the cited code by the triager or a subagent in
  Step 2).

#### `DEFENSE-IN-DEPTH`

Propose when **all** of:

- The reported behaviour is **fact-correct** (the code does
  what the report claims).
- The attack model **falls outside the Security Model boundary**
  — typically: local-user-on-worker (when the model treats
  worker hosts as operator-trusted); legacy-browser-only
  behaviour current browsers block; multi-tenant scenarios the
  project doesn't formally support.
- A public-PR hardening is still desirable on quality grounds
  (e.g. file modes, race windows, scheme allowlists).

The propose-disposition comment should say so explicitly:
*"defense-in-depth fix is welcome via public PR; not a CVE."*

#### `INFO-ONLY`

Propose when **all** of:

- The reported behaviour is fact-correct.
- The behaviour does **not** violate any documented rule, and a
  canned-response template in
  [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md)
  already covers the shape (project-specific heading names come
  from
  [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md)).

`INFO-ONLY` is distinct from `INVALID`: the latter is
typically a *misframing* the team has to explain (and may
warrant an inline-augmented canned response); the former is a
clean *educational* reply where the canned template alone fully
answers the report.

The proposal names the matching canned-response template
explicitly (exact section heading from `canned-responses.md`).

#### `INVALID`

Propose when **any** of:

- The report's technical premise is incorrect (the code does
  not do what the report claims — verified against the cited
  code).
- The framing is *circular* (the report describes a vulnerability
  in code whose purpose is to *fix* that very class of
  vulnerability — typical for upgrade-migration scripts).
- The reported behaviour is documented as *by design* in the
  Security Model or in user-facing docs (cite the URL).
- A previous canned-response precedent applied to a near-identical
  report ended with reporter acceptance.

The proposal cites the specific Security Model section or prior
precedent that grounds the call.

#### `PROBABLE-DUP`

Propose when **any** of:

- A GHSA ID appears in the body and matches a GHSA ID in an
  existing tracker (STRONG match — high-confidence dup).
- The cited code location (file path + function name) matches
  another tracker's *PR with the fix* range — same fix
  presumably covers both.
- A closed advisory describes the same root-cause class and
  the new report is a sibling vector with the same fix shape.

The proposal links the candidate kept-tracker and suggests
`security-issue-deduplicate <new> <existing>` as the next
slash command.

#### `FIX-ALREADY-PUBLIC`

Propose when **all** of:

- The Step 2 *Independent-public-fix detection* surfaced a
  public PR in `<upstream>` (open or merged) that plausibly
  fixes the reported behaviour — same file + function as the
  report's code pointer, title/body matches the vulnerability
  class.
- That PR was **not** filed in response to this tracker
  (i.e. the PR predates the tracker, or the PR author is not on
  the security-team roster and the PR description shows no
  awareness of `<security-list>` or the tracker).
- The report's technical premise is *plausibly correct* —
  enough that the question *"does this PR fix what you
  reported?"* is the load-bearing next step, not *"is this even
  a real issue?"* (if the premise is wrong outright, propose
  `INVALID` instead).

**Reporter credit policy.** Per the
[no-credit-when-fix-is-already-public policy](../issue-import-from-pr/SKILL.md#reporter-credit-policy-for-public-pr-imports)
that this skill inherits from `security-issue-import-from-pr`:
when the fix is already public at the time the report arrives,
the reporter is **thanked but not credited as the finder**, for
the same incentive-alignment reasoning (a public PR is not a
responsible disclosure; awarding finder credit for reports of
already-public fixes trains the next reporter to skip the
private disclosure step). The team can override per-tracker
during Step 5 confirmation if there is a project-specific
reason to credit (e.g. the reporter privately spotted the
issue before the unrelated PR landed).

**Proposal body must include the draft reporter reply.** Per
the read-only-on-tracker contract this skill maintains, the
reply is **not** sent here — it is drafted for the team and
will be sent later via
[`security-issue-invalidate`](../issue-invalidate/SKILL.md)
once the team confirms. Draft template:

> Thanks for the report. We noticed that
> [`<upstream>#<NNN>`](https://github.com/<upstream>/pull/NNN)
> ([`<author>`](https://github.com/<author>), merged YYYY-MM-DD)
> already appears to address what you described. Per our policy,
> we do not credit a finder when the fix to the reported issue
> is already public at the time of report — but we very much
> appreciate you taking the time to write to us.
>
> Could you check whether
> [`<upstream>#<NNN>`](https://github.com/<upstream>/pull/NNN)
> fixes the behaviour you observed? If it does, no further
> action is needed on your side. If after testing with the PR
> you still see the issue, please reply on this thread with
> the failing reproduction and we will reopen the discussion.

Fill in `<NNN>`, `<author>`, and the merge date from the Step 2
detection. If the PR is open (not yet merged), substitute
*"open since YYYY-MM-DD"* for *"merged YYYY-MM-DD"*. If multiple
candidate PRs were surfaced, the draft lists each (the team
trims during Step 5 confirmation).

**Sibling skill hand-off.** After team consensus on the
proposal:

- If the reporter confirms the PR fixes their report →
  [`security-issue-invalidate`](../issue-invalidate/SKILL.md)
  closes the tracker; the reporter-credit field stays blank.
- If the reporter says the PR does **not** fix it →
  re-triage via `--retriage` with the new evidence; the
  classification will typically escalate to `VALID` /
  `DEFENSE-IN-DEPTH` / `INVALID` based on the reporter's
  follow-up.

### Confidence and edge cases

The classifier may emit `UNCERTAIN` internally — surface this
as *"low-confidence proposal, please challenge"* in the comment
body rather than picking one of the six classes blindly. The
team's reply on a flagged-uncertain tracker is what produces
the next iteration; **never** post a high-confidence-toned
proposal when the input state is ambiguous.

### Severity guesses

Per the
["Reporter-supplied CVSS scores are informational only" rule in
`AGENTS.md`](../../../../AGENTS.md), the classifier surfaces a
**severity guess** in the proposal body for context but never
proposes a specific CVSS vector or qualitative score as a
*decision*. The wording is always *"my read is Medium-ish,
team-scoring expected"*, never *"Severity: 7.5 HIGH"*.
