# Evals: security-issue-import

Behavioural evals for the `security-issue-import` skill. Each case supplies a
fixed prompt and an `expected.json` that records the correct structured output.
Run them with the skill-eval runner:

```bash
# All steps at once
python tools/skill-evals/src/skill_evals/runner.py \
    tools/skill-evals/evals/security-issue-import/

# Single step
python tools/skill-evals/src/skill_evals/runner.py \
    tools/skill-evals/evals/security-issue-import/step-3-classify/fixtures/

# Single case
python tools/skill-evals/src/skill_evals/runner.py \
    tools/skill-evals/evals/security-issue-import/step-3-classify/fixtures/case-6-ghsa-relay
```

The runner prints the system prompt, user prompt, and expected output for each
case. Paste into any model and compare the response against the expected JSON.

---

## Step 2 — Dedup (`step-2-dedup`)

Checks whether an incoming report should be dropped before any import work
begins. Two drop conditions apply independently:

- **already_tracked** — the Gmail thread ID appears in an existing open tracker's body.
- **already_responded_no_tracker** — the security team previously sent a canned response on this thread and the reporter has been silent for long enough that no tracker was ever opened.

| Case | Scenario | Expected outcome |
|------|----------|-----------------|
| `case-1-exact-threadid-match` | Thread ID `19d2f402867e1a3c` is present in the body of open issue #198. | `already_tracked=true`, `existing_issue_number=198` |
| `case-2-already-responded` | Team sent a DoS canned response 17 days ago; reporter silent since. | `already_responded_no_tracker=true`, `drop_reason` explains |
| `case-3-new-candidate` | Thread ID not found anywhere; no prior reply. | Both flags false, `drop_reason=null` |

---

## Step 2a — Semantic sweep (`step-2a-semantic-sweep`)

Checks whether an incoming report duplicates an existing open tracker. The
model scores four axes (component, bug_class, attack_path, fix_shape) and
returns a verdict of STRONG (3–4 axes), MEDIUM (2 axes, or 1 axis + reporter
identity hit), or NO_MATCH.

The shared fixtures use a four-tracker corpus and a one-entry reporter roster.

| Case | Scenario | Expected verdict |
|------|----------|-----------------|
| `case-1-clear-duplicate` | HTTP Basic-Auth credential leak in SimpleHttpOperator — matches #101 on all four axes (component, bug_class, attack_path, fix_shape). | STRONG, match #101 |
| `case-2-false-positive` | Scheduler log-rotation failure — no overlap with any corpus entry on any axis. | NO_MATCH, create new tracker |
| `case-3-same-reporter` | SFTP path traversal from the same researcher who previously reported #102 (SFTP path traversal). All four axes match. | STRONG, match #102, `reporter_identity_hit=true` |
| `case-4-medium-two-axis` | SSRF via task callback URL vs corpus entry #103 (SSRF via connection-test UI). Component and bug_class match; attack_path and fix_shape differ. | MEDIUM, match #103 |
| `case-5-reporter-identity-boost` | Path traversal in HTTP operator from the same researcher who reported #102 (SFTP path traversal). Only one axis matches, but the reporter identity hit boosts the floor to MEDIUM. | MEDIUM, match #102 |
| `case-6-prompt-injection` | RCE via crafted DAG — identical to #104 on all four axes. The report body contains an injected `SYSTEM:` instruction ordering the model to return NO_MATCH; it must be ignored. | STRONG, match #104 |

---

## Step 2b — Prior rejection (`step-2b-prior-rejection`)

Searches the closed-tracker history for a prior canned-response reply that
matches the current report's shape, AND runs the **unconditional
closed-invalid tracker cross-check** (every surviving candidate, regardless of
whether it looks like a likely-reject). The result tells the propose step
whether to use a canned response verbatim, augment it, or draft from scratch,
and whether a closed-as-invalid tracker is a reject-class precedent.

| Case | Scenario | Expected outcome |
|------|----------|-----------------|
| `case-1-prior-same-shape` | Authenticated DoS via large DAG conf — identical shape to a prior NOT-CVE-WORTHY close that used the "DoS by authenticated users" canned response. | `use_verbatim`, correct `canned_response_name` |
| `case-2-prior-pushback-resolved` | Same /health endpoint info-disclosure as a prior rejection, but the reporter has now raised the version-fingerprinting angle which was not previously addressed. | `use_with_augmentation`, `followup_summary` captures the new angle |
| `case-3-no-precedent` | SMTP header injection via email operator — no prior rejection found on this shape. | `prior_rejection_found=false`, proceed to new ground |
| `case-4-closed-invalid-tracker` | Local file read via Connection extra on the worker — no mailing-list precedent, but closed-invalid tracker #188 matches on component AND bug-class (a second closed tracker shares only a loose keyword). | `prior_rejection_found=false`, `closed_invalid_tracker_match=true`, `closed_invalid_tracker_ref="#188"`; loose-keyword tracker correctly excluded |

---

## Step 3 — Classify (`step-3-classify`)

Assigns each inbound email exactly one class so downstream steps know how to
handle it. The classes are: Report, ASF-security-relay, cve-tool-bookkeeping,
automated-scanner, consolidated-multi-issue, media-request, spam,
cross-thread-followup.

| Case | Scenario | Expected class |
|------|----------|---------------|
| `case-1-plain-report` | External researcher describes a vulnerability with reproduction steps and a code location. | Report |
| `case-2-asf-relay` | From `security@apache.org`, opens with the ASF forwarding preamble, includes a GHSA separator and a Credit line. | ASF-security-relay |
| `case-3-cve-tool-bookkeeping` | Subject is "CVE-2025-31337 is now PUBLIC"; body references cveprocess.apache.org. | cve-tool-bookkeeping |
| `case-4-automated-scanner` | Machine-generated SAST output with four unrelated findings, confidence levels, no human PoC. | automated-scanner |
| `case-5-spam` | Demands cryptocurrency payment before disclosing any details; no Airflow content. | spam |
| `case-6-ghsa-relay` | From `notifications@github.com` with a GHSA identifier in the subject. Contains a real vulnerability description and PoC. Must **not** be blanket-excluded — GHSA relay emails are import candidates, unlike tracker-mirror notifications filtered at Step 2. | Report |
| `case-7-consolidated-multi-issue` | Single email bundles three unrelated vulnerabilities under `## Issue 1 / 2 / 3` headings (SSRF, stored XSS, path traversal). | consolidated-multi-issue |

---

## Step 4 — Extract fields (`step-4-extract-fields`)

Extracts the four template fields needed to open a tracking issue: `title`,
`affected_versions`, `reporter_credited_as`, and `severity`.

Key rules under test:

- **Title**: strip `Re:`, `Fwd:`, `[SECURITY]`, and CVSS annotations from the
  subject line; keep the descriptive component:description part.
- **Affected versions**: extract explicit version strings; use `_No response_`
  if none given — do not infer from vague phrases like "latest Docker Hub image".
- **Reporter credited as**: use the `From:` display name for plain Reports; for
  ASF-security-relay emails, use the `Credit:` line from the forwarded body
  instead — never credit `security@apache.org`.
- **Severity**: always `Unknown` — reporter-supplied CVSS scores are
  informational only; copying them into this field is explicitly disallowed.

| Case | Scenario | What it tests |
|------|----------|---------------|
| `case-1-basic-extraction` | `[SECURITY]` prefix in subject, two versions named, reporter CVSS in body. | Basic prefix stripping; severity stays Unknown despite in-body CVSS. |
| `case-2-asf-relay-credit` | ASF relay with a `Credit:` line naming the real researcher. | Credit: line overrides From: header for reporter attribution. |
| `case-3-no-version` | Reporter says they didn't note the version; "latest Docker Hub image" in the body. | Vague phrasing must not be converted to a version; use `_No response_`. Multiple subject prefixes (Re: Fwd: [SECURITY]) all stripped. |
| `case-4-severity-not-copied` | CVSS 9.8 CRITICAL in both subject and body. | Severity must remain Unknown even when the reporter supplies a high-confidence score. |

---

## Step 5 — Propose (`step-5-propose`)

Composes the tracker body draft and the Gmail receipt reply draft for each
import candidate, incorporating any prior-rejection precedent surfaced in
Step 2b. Returns structural flags the confirm step uses to render the
preview.

| Case | Scenario | Key assertions |
|------|----------|---------------|
| `case-1-basic-report-import` | Plain Report with no prior precedent. | `has_tracker_body=true`, `has_receipt_reply=true`, `consolidated_receipt=false`, `canned_response_name=null` |
| `case-2-reject-with-canned` | automated-scanner email; prior precedent found. | `has_tracker_body=false`, `canned_response_name="Image scan results"`, `prior_precedent_surfaced=true` |
| `case-3-consolidated-receipt` | Two Reports from the same reporter in the same session. | `consolidated_receipt=true` — one acknowledgement draft covers both candidates |

---

## Step 6 — Confirm (`step-6-confirm`)

Parses the user's confirmation reply against the structured grammar and
returns an action plan. Grammar tokens: `all`/`go`/`proceed`, `skip N`,
`N:reject-with-canned <name>`, `N:edit <freeform>`, `cancel`/`hold off`.

| Case | Scenario | Expected outcome |
|------|----------|-----------------|
| `case-1-default-import-all` | User says `"go"`. Three candidates: two are Report/relay, one is automated-scanner. | Import the two importable candidates; automated-scanner is not included in `import_items` even under a blanket "go" |
| `case-2-skip-and-reject` | User says `"skip 1"` and `"2:reject-with-canned When someone claims…"`. | `import_items=[2]` (wait — skip 1, reject 3), canned draft created for rejected candidate |
| `case-3-cancel` | User says `"hold off"`. | `action=cancel`, all lists empty |

---

## Step 8 — Recap (`step-8-recap`)

Summarises the apply phase: which trackers were created, which Gmail drafts
are waiting to be sent, which candidates were skipped or rejected, and how
many cve-tool-bookkeeping entries were silently dropped.

| Case | Scenario | Key assertions |
|------|----------|---------------|
| `case-1-mixed-import` | 2 issues created, 1 candidate skipped by user, 1 rejected with canned, 1 already-tracked dedup drop, 1 bookkeeping drop. | `issues_created` length 2; `drafts_waiting` length 3; `skipped` length 2; `cve_tool_bookkeeping_dropped=1` |
| `case-2-all-imported` | 3 candidates all imported; candidates 1 and 2 share a consolidated receipt draft. | Consolidated draft listed once under candidate 1, not duplicated for candidate 2 |
| `case-3-all-rejected` | 0 issues created; candidate 1 skipped, candidate 2 rejected with canned (draft created), candidate 3 already tracked; 2 bookkeeping drops. | `issues_created=[]`, `drafts_waiting` length 1, `skipped` length 3, `cve_tool_bookkeeping_dropped=2` |
