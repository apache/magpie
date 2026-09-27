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

**Backend selection.** Candidate listing is one of the cases where
**Gmail remains primary even when PonyMail MCP is enabled**: the
inbox is where just-arrived inbound reports land with the lowest
latency, and the import skill's sole purpose is converting
those freshly-arrived threads into trackers. The PonyMail archive
lags the inbox by minutes-to-hours for brand-new messages, which
is exactly the window this skill most cares about.

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

Cross-reference the returned summaries against the Gmail result
set by `Message-ID`. Surface two classes of mismatch as extra
candidates in Step 5:

- **In PonyMail, not in Gmail** → note *"seen in the archive, not
  in this user's Gmail — LDAP-only subscription, Gmail-filter
  miss, or wrong account"*. Often worth importing; always worth
  surfacing.
- **In Gmail, not in PonyMail** → note *"in Gmail inbox, not yet
  in the archive — archive-indexing lag; Gmail snapshot is the
  authoritative source for now"*. Proceed with Gmail-only data
  for this thread; a future sync run will reconcile once the
  archive catches up.

When PonyMail MCP is disabled, unauthenticated, or the private
list is not in the user's allowlist, skip the paired-check query
and proceed Gmail-only.

**Do not exclude `-from:<security-list>`.** That address is used
for three very different message types — CVE-tool bookkeeping,
**ASF Security Team forwarding of inbound reports**, and ad-hoc ASF
Security discussion / advice. Blanket-excluding the sender would drop
the forwarded reports along with the bookkeeping noise, so the
bookkeeping emails are filtered out at Step 3 by subject pattern
instead — see the `cve-tool-bookkeeping` row of the classification
table.

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

Filter the mirror notifications at Step 1 only by the project's
declared dedicated `noreply` mirror addresses (e.g.
`<tracker-repo>@noreply.github.com`, declared in
[`<project-config>/project.md`](../../../../<project-config>/project.md#gmail-and-ponymail)).
**Do not blanket-exclude `notifications@github.com`** — the
remaining tracker-mirror chatter on `notifications@github.com` is
caught at Step 2 (threadId dedup against existing tracker bodies)
and Step 2-bis (already-answered detection).

The canonical query template in
[`tools/gmail/search-queries.md`](../../../../tools/gmail/search-queries.md#security-issue-import--candidate-listing-query)
omits the blanket exclusion; project-specific `<project-config>/project.md`
declarations enumerate dedicated mirror noreply senders only.

**Mandatory second pass — run a positive GHSA query.** The rule above
is a *negative* one, and negative rules are not self-enforcing: an
exclusion added anywhere for noise reduction removes the whole GHSA
intake channel, and the miss is invisible — nothing reports that a
report was filtered out. So every import scan **also** runs the
[GHSA-advisory query](../../../../tools/gmail/search-queries.md#security-issue-import--ghsa-advisory-query-mandatory-second-pass),
which checks the channel by construction and cannot be filtered away
by an exclusion elsewhere. Union its hits with the candidate-listing
query's before Step 2.

For each hit whose subject carries `[<upstream>] ... (GHSA-...)`:

- Treat it as a **`Report`** candidate, not tracker-mirror noise.
- The advisory **body is confidential** — it lands in the private
  tracker only, per the confidentiality golden rule; never echo it to
  a public surface.
- Prefer the advisory **record API**
  (`gh api repos/<upstream>/security-advisories/<GHSA>`). **If it
  404s, the operator is not yet a collaborator on that specific
  advisory** — this is an access state, not a missing advisory.
  Extract the report from the notification email body and flag the
  **admin hand-off**: someone with advisory-admin rights must add the
  operator as a collaborator before the record API and the
  reporter-reply path become usable. See the GHSA contract in
  [`security-issue-sync`'s `github-advisory.md`](../issue-sync/github-advisory.md).

Adjust the time window per the user's selector (`since:` → `newer_than:`
or `after:`; `import all` → `newer_than:90d`).

Run the query via `mcp__claude_ai_Gmail__search_threads` (see
[`tools/gmail/operations.md`](../../../../tools/gmail/operations.md#search-threads)).
For each result, record `threadId` — the downstream de-duplication
hinges on this.

**Do not read the thread bodies yet.** Body reads cost Gmail budget and
most threads will be filtered out at Step 2.

---
