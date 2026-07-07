<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — canned responses](#todo-project-name--canned-responses)
  - [TODO — minimum viable canned responses](#todo--minimum-viable-canned-responses)
    - [Confirmation of receiving the report](#confirmation-of-receiving-the-report)
    - [Negative assessment — out of scope per the Security Model](#negative-assessment--out-of-scope-per-the-security-model)
    - [Negative assessment — not a vulnerability](#negative-assessment--not-a-vulnerability)
  - [TODO — common "known-invalid" categories](#todo--common-known-invalid-categories)
    - [Automated scanning results](#automated-scanning-results)
    - [Consolidated multi-issue report](#consolidated-multi-issue-report)
    - [Media / research-disclosure request](#media--research-disclosure-request)
    - [Publicly-disclosed issue (reported after public disclosure)](#publicly-disclosed-issue-reported-after-public-disclosure)
  - [TODO — status-update templates](#todo--status-update-templates)
    - [CVE allocated (Step 6)](#cve-allocated-step-6)
    - [Fix PR opened (Step 10)](#fix-pr-opened-step-10)
    - [Fix PR merged (Step 11)](#fix-pr-merged-step-11)
    - [Release shipped (Step 12)](#release-shipped-step-12)
    - [Advisory sent (Step 13)](#advisory-sent-step-13)
    - [CVE published on cve.org (post-Step 15)](#cve-published-on-cveorg-post-step-15)
    - [Credit correction (Step 16)](#credit-correction-step-16)
  - [Drafting rules](#drafting-rules)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — canned responses

Reusable reporter-facing reply templates. These are sent **verbatim**
as email replies on the original inbound thread, so tone matters —
follow the *"Tone: polite but firm"* and *"Brevity: emails state
facts, not context"* rules in
[`../../AGENTS.md`](../../AGENTS.md). Every template links into the
project's Security Model (see
[`security-model.md`](security-model.md)) rather than paraphrasing
it.

The [`security-issue-import`](../../skills/security-issue-import/SKILL.md)
skill sends the *Confirmation of receiving the report* template
verbatim on every new inbound report — that one is **load-bearing**
and must exist before the skill is useful. The rest can be filled in
gradually as real reports surface categories the team wants to
canonicalise.

## TODO — minimum viable canned responses

At a minimum, the following templates should exist before a tracker
team goes live. The shapes are stubbed below; adapt the wording to
the adopting project's voice.

### Confirmation of receiving the report

TODO: short confirmation that the report has been received, the
security team will assess it, and what the reporter should expect
next. Include the credit-preference question. Sent verbatim by
`security-issue-import`.

### Negative assessment — out of scope per the Security Model

TODO: polite-but-firm reply used when a report describes behaviour
the project's Security Model explicitly considers out of scope.
Link to the specific Security-Model chapter.

### Negative assessment — not a vulnerability

TODO: reply for reports that describe a bug or design question that
is not a vulnerability.

## TODO — common "known-invalid" categories

Fill these in as the team encounters repeat categories. Each template
is addressed to a specific reporter shape (automated scanner,
consolidated multi-issue report, media-disclosure request, etc.).

### Automated scanning results

TODO.

### Consolidated multi-issue report

TODO.

### Media / research-disclosure request

TODO.

### Publicly-disclosed issue (reported after public disclosure)

TODO.

## TODO — status-update templates

Every lifecycle transition that the team commits to notifying the
reporter about (per
[`../../docs/security/roles.md#keeping-the-reporter-informed`](../../docs/security/roles.md#keeping-the-reporter-informed))
needs a short template. Skills draft from these verbatim and send
on the original inbound thread.

The **Brevity** shape from [`../../AGENTS.md`](../../AGENTS.md)
applies to every one of these: three paragraphs at most —
*what changed / what comes next / artifact URL*.

Minimum set (one per lifecycle transition):

| Template | Process step | Sent by |
|---|---|---|
| CVE allocated | Step 6 | `security-cve-allocate` skill |
| Fix PR opened | Step 10 | `security-issue-fix` / `security-issue-sync` skill |
| Fix PR merged | Step 11 | `security-issue-sync` skill |
| Release shipped (fix released) | Step 12 | `security-issue-sync` skill |
| Advisory sent | Step 13 | Release manager + `security-issue-sync` follow-up |
| CVE published on cve.org | post-Step 15 | `security-issue-sync` skill (recently-closed scan) |
| Credit correction | Step 16 | Release manager |

Each row above corresponds to a section below; flesh out the
template body with project-specific wording.

### CVE allocated (Step 6)

TODO: one paragraph stating the CVE has been allocated, one stating
the advisory will be sent when the fix ships, one line with the
CVE-tool record URL.

### Fix PR opened (Step 10)

TODO: one paragraph stating the fix PR is now public (with the note
that its description is scrubbed of security-nature signals), one
stating the advisory follows on release, one line with the fix-PR
URL.

### Fix PR merged (Step 11)

TODO: one paragraph stating the fix has merged + the target release
it will ship in, one stating the advisory will go to the project's
users and announce lists when that release ships, one line with the
merged PR URL.

### Release shipped (Step 12)

TODO: one paragraph stating the release has shipped, one stating
the release manager will send the advisory next + we will follow
up when archived, one line with the release-tag URL.

### Advisory sent (Step 13)

TODO: one paragraph stating the advisory has been sent + release
is live, one stating a final note will follow once the CVE
propagates to cve.org, one line with the advisory-archive URL.

### CVE published on cve.org (post-Step 15)

TODO: one paragraph stating the CVE is now live on cve.org and the
disclosure process is complete, one "thank you for the responsible
disclosure" line, one line with the `https://www.cve.org/CVERecord?id=<CVE-ID>`
URL.

### Credit correction (Step 16)

TODO: one paragraph stating the credits have been corrected, one
stating the update has been pushed to cve.org, one line with the
updated record URL.

## Drafting rules

- **Do not paraphrase the Security Model.** Link to the chapter.
- **Do not echo reporter-supplied CVSS scores.** See the rule in
  [`../../AGENTS.md`](../../AGENTS.md#reporter-supplied-cvss-scores-are-informational-only--never-propagate-them).
- **Tracker URLs are public-safe identifiers** per the
  [Confidentiality of `<tracker>`](../../AGENTS.md#confidentiality-of-the-tracker-repository)
  rule and *may* appear in these templates (typically as a
  `Tracker reference: TRACKER_URL (private; identifier only — page
  will 404 for you)` line on status updates). Tracker *contents*
  (comment quotes, label transitions, body excerpts) and the
  ASF-OAuth-gated CVE-tool URL (`cveprocess.apache.org/cve5/...`)
  must not appear in templates that go out as email — they remain
  internal-only.
- **Every transition that warrants a reply is listed in
  [`../../docs/security/roles.md`](../../docs/security/roles.md#keeping-the-reporter-informed)** —
  treat that list as authoritative.
