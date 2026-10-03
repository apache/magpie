<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — candidate listing

## Step 1 — List candidate threads from Gmail

Search `<security-list>` for inbound reports, excluding the
tooling / GitHub-notification / mailing-list chatter that isn't a
report:

Use the canonical candidate-listing query template from
[`tools/gmail/search-queries.md`](../../../../tools/gmail/search-queries.md#security-issue-import--candidate-listing-query);
substitute the adopting project's `<security-list-domain>` and the
project's GitHub-notification exclusions — both declared in
[`<project-config>/project.md`](../../../../<project-config>/project.md#gmail-and-ponymail).

**Backend selection.** Here **Gmail remains primary even when PonyMail MCP is enabled**:
the archive lags the inbox by minutes to hours for brand-new messages, exactly the threads this skill exists to import.

When PonyMail MCP is enabled and authenticated (Step 0) **and**
`<security-list>` is in `.apache-magpie-overrides/user.md` →
`tools.ponymail.private_lists`, run the archive as a **paired
authoritative check** against the Gmail result set:

```text
mcp__ponymail__search_list(
  list: "security",
  domain: "<project>.apache.org",
  timespan: "lte=30d",
  emails_only: true
)
```

Cross-reference the returned summaries against the Gmail result set by `Message-ID`.
Surface two classes of mismatch as extra candidates in Step 5:

- **In PonyMail, not in Gmail** → note *"seen in the archive, not
  in this user's Gmail — LDAP-only subscription, Gmail-filter
  miss, or wrong account"*. Often worth importing; always worth
  surfacing.
- **In Gmail, not in PonyMail** → note *"in Gmail inbox, not yet
  in the archive — archive-indexing lag; Gmail snapshot is the
  authoritative source for now"*. Proceed with Gmail-only data
  for this thread; a later sync reconciles it.

When PonyMail MCP is disabled, unauthenticated, or the private
list is not in the user's allowlist, skip the paired-check query
and proceed Gmail-only.

**Do not exclude `-from:<security-list>`.** That address carries CVE-tool bookkeeping,
**ASF Security Team forwarding of inbound reports**, and ad-hoc ASF Security discussion / advice;
excluding it would drop the forwarded reports.
Bookkeeping is filtered by subject pattern instead — by the
[Step 1 pre-filter](#step-1-pre-filter--classes-decidable-from-subject-and-sender) below,
with the `cve-tool-bookkeeping` row of the Step 3 classification table as the backstop for the body-line variant.

**Do not exclude `-from:notifications@github.com` wholesale.** GitHub
uses this address for **two distinct categories** of messages:

1. **Tracker-mirror notifications** — when an action lands on a
   tracker issue (comment, label, close), GitHub emails every
   subscriber. These arrive with subject `[<tracker-repo>] ...`
   and are *not* import candidates — they describe an existing
   tracker.
2. **GHSA-relayed reports** — when a reporter files a GitHub
   Security Advisory against `<upstream>`, GitHub emails
   `notifications@github.com → <security-list>`
   with subject `[<upstream>] ... (GHSA-...)`. **These are**
   import candidates. A GHSA relay is not a distinct class — at
   Step 3 classify it as a plain **`Report`** (the GHSA ID is
   captured as a de-dup signal and as provenance, not as the
   classification) and proceed to field extraction.

Filter the mirror notifications at Step 1 only by the project's declared dedicated `noreply` mirror addresses
(e.g. `<tracker-repo>@noreply.github.com`, declared in
[`<project-config>/project.md`](../../../../<project-config>/project.md#gmail-and-ponymail));
the canonical query template already omits the blanket exclusion.
The remaining tracker-mirror chatter on `notifications@github.com` is caught at Step 2 (threadId dedup against existing tracker bodies)
and Step 2-bis (already-answered detection).

**Mandatory second pass — run a positive GHSA query.** A negative rule is not self-enforcing:
an exclusion added anywhere for noise reduction silently removes the whole GHSA intake channel.
So every import scan **also** runs the
[GHSA-advisory query](../../../../tools/gmail/search-queries.md#security-issue-import--ghsa-advisory-query-mandatory-second-pass),
which checks the channel by construction.
Union its hits with the candidate-listing query's before Step 2.

For each hit whose subject carries `[<upstream>] ... (GHSA-...)`:

- Treat it as a **`Report`** candidate, not tracker-mirror noise.
- The advisory **body is confidential** — see the confidentiality golden rule.
- Prefer the advisory **record API** (`gh api repos/<upstream>/security-advisories/<GHSA>`).
  **If it 404s, the operator is not yet a collaborator on that specific advisory** — an access state, not a missing advisory.
  Extract the report from the notification email body and flag the **admin hand-off**:
  someone with advisory-admin rights must add the operator as a collaborator before the record API and the reporter-reply path work.
  See the GHSA contract in [`security-issue-sync`'s `github-advisory.md`](../issue-sync/github-advisory.md).

Adjust the time window per the user's selector (`since:` → `newer_than:`
or `after:`; `import all` → `newer_than:90d`).

Run the query via `mcp__claude_ai_Gmail__search_threads` (see
[`tools/gmail/operations.md`](../../../../tools/gmail/operations.md#search-threads)).
For each result, record `threadId`; downstream de-duplication hinges on it.

**Do not read the thread bodies yet:** most threads are filtered out at Step 2.

### Step 1 pre-filter — classes decidable from subject and sender

Some candidate classes are decided by the subject line and the sender alone.
Apply them here, to the union of the candidate-listing, GHSA and PonyMail-paired results, so those threads never reach the Step 2 search, the Step 2-bis MINIMAL read, or the Step 2a `FULL_CONTENT` fetch.
This is a pre-flight no-op classifier in the sense of `security-issue-sync`'s [bulk-mode Step 1b](../issue-sync/bulk-mode.md): deterministic, conservative, and never silent.

**Inputs.** Only the subject and `From:` address the search result carries for each message of the thread, plus `<tracker>`, `<upstream>` and `<security-list>` from [`<project-config>/project.md`](../../../../<project-config>/project.md).
Drop a thread only when **every** message the result lists for it matches the **same** rule; a result that carries no subject or no sender keeps the thread.
Never read a body to decide.

**Rules**, applied in order; the first match wins:

| # | Rule | Decision |
|---|---|---|
| 1 | Subject carries a `GHSA-` token, sender is `notifications@github.com`, and the subject begins with `[<upstream>]` | **Keep**, pre-tagged as a GHSA relay. It is a `Report` candidate whose body is needed. |
| 2 | Sender satisfies the sender condition of the Step 3 [`cve-tool-bookkeeping` row](SKILL.md#step-3--classify-each-candidate), **and** the whole subject matches one of that row's subject patterns, with `CVE-YYYY-NNNNN` read as `CVE-\d{4}-\d{4,7}` and no `Re:` / `Fwd:` / other prefix | **Pre-filter** as `cve-tool-bookkeeping`. The row's other trigger — a state-change line in the body — needs the body, so it stays at Step 3. |
| 3 | Anything else | **Keep** — Steps 2 to 3 decide. |

Tracker-mirror chatter is left to Step 2 and Step 2-bis, as before.
Every other class (`automated-scanner`, `consolidated-multi-issue`, `media-request`, `spam`, `cross-thread-followup`, `fix-already-public`, forwarder relays, and the body-line variant of `cve-tool-bookkeeping`) needs the body and is **never** pre-filtered.

**Hard rules.**

- **Never silent.** Every pre-filtered thread is recorded with its `threadId`, sender, subject, class and rule number.
  Step 5 shows the per-class counts and Step 8 lists each thread, per [Step 5](screening-and-proposal.md#step-5--propose-the-imports) and [Step 8](SKILL.md#step-8--recap).
  The user can send any of them back through Steps 2 to 3 with `keep <threadId>` at Step 6.
- **A named thread is never pre-filtered.** Under `import thread:<id>` the rules are evaluated for context only; Step 3 classifies the thread as usual.
- **Borderline means keep.** A subject that only resembles a pattern (a `Re:` prefix, a different CVE-token shape, an extra suffix) keeps the thread, and Step 3 still applies its table.

---
