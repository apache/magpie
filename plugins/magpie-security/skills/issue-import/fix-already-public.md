<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — fix-already-public search

## Step 2c — Search `<upstream>` for an already-public fix

Step 2c covers a third no-tracker-needed case (after Step 2a's overlapping trackers and Step 2b's prior rejections):
an **independent public PR in `<upstream>` already appears to fix the reported behaviour**.
Rather than open a tracker the team would later close through `security-issue-invalidate`,
thank the reporter, point at the PR, ask them to verify, and skip tracker creation.

**Run Step 2c on** every `Report` or forwarder-relayed candidate that Step 2a did *not* flag STRONG
(STRONG routes to `security-issue-deduplicate`).
Skip candidates whose provisional class (the Step 2a pre-classification) is `automated-scanner`,
`consolidated-multi-issue`, `media-request`, `spam`, `cve-tool-bookkeeping`, or `cross-thread-followup`.
(Threads the Step 1 pre-filter dropped as `cve-tool-bookkeeping` never reach this step.)

**Detection signals** (any one is sufficient to surface the
candidate as a potential `fix-already-public`):

1. **Reporter links to a public PR.** The body contains an
   `https://github.com/<upstream>/pull/<N>` URL — the most reliable signal.
2. **Code-pointer + vulnerability-class match in a recent PR.**
   For each code pointer extracted in Step 2a (file path + function name),
   search `<upstream>` for PRs that touch that surface and whose title/body matches the candidate's vulnerability class
   (e.g. *escape*, *sanitize*, *validate*, *auth*, *XSS*, *CVE*, *security*).
   Use the temp-file pattern from Step 2a (key 3) — never put report-derived strings directly into the `gh search prs` argument.

   Compute `<since-date>` yourself as today minus 180 days, in `YYYY-MM-DD` form, and write the literal date into the qualifier
   — no `date` command substitution, so the `gh` call stays a plain command:

   Write the keywords to `<scratch>/pubfix-kw-<threadId>.txt` with the Write tool, clean them as in Step 2a:

   ```bash
   tr -cd 'A-Za-z0-9._ -' < <scratch>/pubfix-kw-<threadId>.txt > <scratch>/pubfix-kw-<threadId>.clean.txt
   ```

   then read the cleaned file and run each search as a plain command, keywords single-quoted:

   ```bash
   gh search prs '<cleaned keywords>' --repo <upstream> \
     --merged --merged-at ">=<since-date>" \
     --json number,title,author,closedAt,url --limit 10
   ```

   ```bash
   gh search prs '<cleaned keywords>' --repo <upstream> --state open \
     --json number,title,author,createdAt,url --limit 10
   ```

   `gh search prs` has no `mergedAt` JSON field; for the merged search,
   `closedAt` is the merge date (the `--merged` filter guarantees every
   hit was merged).

3. **GHSA cross-reference.** If the body contains a `GHSA-…` ID
   that Step 2a did *not* match against an existing tracker,
   search `<upstream>` for a PR that references that GHSA — some
   projects file the GHSA-linked fix PR before the tracker exists.

**Budget guardrail for Step 2c**: **≤ 3 `gh search prs` calls per candidate** (signals 1 + 2 + 3 above).
If signal 1 finds a reporter-supplied PR URL, skip signals 2 and 3.

**Match grading**:

- **STRONG** — reporter linked the PR explicitly, OR the matched
  PR's title/body explicitly names the same vulnerability class
  on the same code surface (e.g. report says *"XSS in
  `app/www/security/permissions.py:render_label`"* and the
  PR title is *"Escape user-supplied label in `permissions.py`
  to fix XSS"*).
- **MEDIUM** — code surface matches and the vulnerability class
  is plausible from the PR's diff scope, but the title is
  generic (*"Fix permissions handling"*).
- **WEAK** — same file but unrelated function, or same function
  but a refactor PR with no security framing.

Only STRONG matches route to `fix-already-public` in Step 3.
MEDIUM matches surface as an *informational* note on the candidate's proposal entry
(the triager may switch it to `fix-already-public` at confirmation after reading the PR).
WEAK matches are ignored.

**PR-was-filed-in-response check.** Before grading a match
STRONG, confirm the PR was **not** filed *because of* this
report. Heuristics:

- PR author is on the security-team roster (cached at Step 0)
  AND the PR creation date is *after* the candidate's email
  arrival → likely filed in response; downgrade to a regular
  `Report` candidate and let triage handle the credit
  question.
- PR description references the `<security-list>` thread or
  contains language like *"reported via security@"* → same
  treatment.
- PR creation date is **before** the candidate's email arrival
  → independent fix; STRONG match stands.

**Surfacing in Step 5.** For each STRONG match, attach to the
candidate's proposal entry:

- a clickable PR link, author handle, merge state + date;
- a one-line *"this PR appears to fix the reported behaviour"*
  rationale;
- a draft *thank-without-credit + verify-with-PR* reply (shape
  in Step 5).

For MEDIUM matches, attach the PR link with *"possible match,
review before deciding"* framing — no draft reply unless the
user upgrades to STRONG during confirmation.

**Hard rule**: Step 2c is **read-only**: no comment on the PR, and no draft until Step 7 applies the confirmed disposition.
The PR stays unaware of the report, per `security-issue-import-from-pr`'s
[*no outreach to the PR author about the CVE*](../issue-import-from-pr/SKILL.md#reporter-credit-policy-for-public-pr-imports) rule.

---
