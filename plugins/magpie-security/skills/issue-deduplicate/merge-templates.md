<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-deduplicate — merged body and rollup-entry templates

## Step 3 — Build the merged body proposal

The output is a single body that preserves both reporters' content
verbatim. The body-field schema (role names, empty-field convention,
body-field-surgery pattern) is documented in
[`tools/github/issue-template.md`](../../../../tools/github/issue-template.md);
the concrete field names for the adopting project live in
[`<project-config>/project.md`](../../../../<project-config>/project.md#issue-template-fields).
Structure:

```markdown
### The issue description

<keep.issue_description verbatim>

---

**Second independent report: [<tracker>#<drop>](https://github.com/<tracker>/issues/<drop>) — merged on <YYYY-MM-DD>.** <one-sentence headline: same root-cause bug, different attack vector / affected process.>

<details>
<summary>Full report from <drop.reporter> (click to expand)</summary>

<one-paragraph summary of WHY the two reports are the same root-cause
bug — same function, same file, same allowlist fix — but describe
different attack vectors / affected processes / threat-model
boundaries. This paragraph is the skill's own analysis, written
for a future triager who wants to understand why the two were
merged; write it so it reads naturally even after the duplicate
tracker has been closed for months.

<drop.issue_description verbatim>

</details>

### Short public summary for publish

<merged summary covering both vectors; if either side was `_No
response_`, use the populated side; if both were populated,
combine them with a leading sentence that covers both attack
vectors explicitly — the release manager will refine at Step 13>

### Affected versions

<widen the range to the broader of the two — take the lower `version
`-bound and the higher `lessThan` upper bound from both sides>

### Security mailing list thread

<keep.reporter> (<keep.context>): <keep's thread URL or Gmail threadId note>
<drop.reporter> (<drop.context>): <drop's thread URL or Gmail threadId note>
```
(one line per reporter; keep them in chronological order of the
original report, earliest first)

```markdown
### Public advisory URL

<keep's value; normally _No response_ at the time of merge>

### Reporter credited as

<keep.credit line verbatim>
<drop.credit line verbatim>
```
(one line per credit; preserve the *exact* form each reporter
confirmed, or the placeholder form when unconfirmed; the merge
does not silently re-synthesize credits)

**Apply the [bot/AI credit policy](../../../../tools/cve-tool-vulnogram/bot-credits-policy.md)
(at `tools/<cve-tool>/bot-credits-policy.md`) when consolidating.** If either tracker carries a credit line on
the **finder side** (*Reporter credited as*) that matches the bot
detection rule (`*[bot]` suffix, known-bot list,
`*-bot`/`*-ai`/`*-agent`/`*-gpt` / `*scanner*` / `*automat*`
suffix patterns, automation-name list), propagate the line into
the kept tracker's *Reporter credited as* field unchanged — the
CVE JSON generator emits it with `type: "tool"` per the policy's
finder-side rule. Surface in the proposal *"credited as tool
(during merge): `<line>` (matches bot policy — `<rule>`)"* with
the source tracker number so the user can see which rows are
being routed as tools. If the drop tracker has an inbound
reporter thread to reply on, also propose the policy's
*clarification-reply* Gmail draft asking whether a human behind
the bot/AI handle should be **additionally** credited as finder.
The user can override per the policy doc.

For the **remediation-developer side**, the dedup still applies
the original *skip* rule: a bot-matching line in either tracker's
*Remediation developer* field is dropped from the merge result
(no `type: "tool"` mapping exists for remediation-developer
credits — see the policy doc). Surface *"skipped credit
(during merge): `<line>` (matches bot policy — `<rule>`)"* for
remediation-side rows.

Manual credits that a human security-team member typed in
(visible in the issue timeline) are always preserved verbatim
on both sides — the filter only fires on credit lines that were
auto-extracted upstream.

```markdown
### PR with the fix

<keep's value, or merge if both are populated>

### CWE

<the more specific of the two values; if they disagree on the
primary CWE, surface the disagreement as a blocker for the
triager rather than silently picking one>

### Severity

<keep's value; do NOT propagate a reporter-supplied CVSS from the
dropped tracker into the kept tracker's Severity field — the
independent-scoring rule in AGENTS.md applies to merged content
the same way it applies to a single reporter's content>

### CVE tool link

<keep's value>
```

The **Second independent report** block is the load-bearing part of
the merge. It lets every future triager read both reports in one
place without having to chase the closed duplicate's content.
Append the drop side's body **verbatim except for reporter-supplied
CVSS scores, CVSS vectors, and qualitative severity labels** inside
the `<details>` disclosure — preserve the reporter's wording, code
blocks, and PoC text. Do not paraphrase; paraphrasing a security report is how
credits get subtly wrong before publication. The short headline that
stays visible at the top of the `<details>` block is a one-sentence
summary for scroll-readers; clicking expands to the full verbatim
report. This is the same short-headline-over-collapsed-details
pattern the status-change comments use, applied to the body so a
long secondary report does not push every other body field below
the fold.

If the drop-side body already had a *"Second independent report"*
`<details>` block (chain-merge case — rare), nest its content
inside the new outer block (or append as a sibling sub-block) so
the chain of merges stays visible. Never flatten or rewrite earlier
merges.

## Step 4 — Build the rollup-entry proposals

Two rollup-comment entries, one per tracker — **not** two new
top-level comments. The entries are appended to each tracker's
existing status-rollup comment (created by `security-issue-import`)
via the upsert recipe in
[`tools/github/status-rollup.md`](../../../../tools/github/status-rollup.md#upsert-recipe--append-to-an-existing-rollup-or-create-one).
When either tracker does not yet carry a rollup (legacy tracker
pre-dating the convention), the upsert recipe's Step 2b creates
one and folds any pre-existing legacy bot comments in on the way.

Each entry is a single `<details>` block. Follow the zero-whitespace
rules from the shared spec — no leading spaces inside the block,
one blank line after `<summary>…</summary>`, one blank line
before `</details>`.

### Entry appended to the kept tracker's rollup

```markdown
<details><summary><YYYY-MM-DD> · @<author-handle> · Merge (kept) (from #<drop>)</summary>

**Merged [<tracker>#<drop>](https://github.com/<tracker>/issues/<drop>) into this tracker.** <one-sentence headline: same root-cause bug, different attack vector / affected process.>

- Body: <keep.reporter>'s original report preserved; <drop.reporter>'s report appended as *"Second independent report"*.
- Credits: **<keep credit>** + **<drop credit>**.
- Mailing threads: both listed.
- CVE: [<CVE-N>-<M>](<cve-record-url>) stays allocated here; [<tracker>#<drop>](https://github.com/<tracker>/issues/<N>) being closed as duplicate. The `<cve-record-url>` form is assembled from `cve_authority.record_url_template` in [`<project-config>/project.md`](../../../../<project-config>/project.md#cve-authority).

**Next:** <one-line next step — e.g. credit-preference confirmation for both, or Step 6 CVE refinement>.

<Reporter-notification line — one of the four canonical options from the sync skill.>

Full analysis of why the two reports are the same root-cause bug (same function, same file, same allowlist fix) but describe different attack vectors / affected processes / threat-model boundaries. Per-field hand-off details:

- *Reporter credited as*: <full before → after>.
- *Security mailing list thread*: <full before → after, including PonyMail URLs and Gmail thread IDs>.
- *Short public summary for publish*: <kept as-is | seeded with a merged draft starting "..."/>.
- *CWE*: <set to <value> | kept as _No response_ | BLOCKER: conflict between <keep.cwe> and <drop.cwe> — triager to resolve>.
- *Affected versions*: widened to <value>.
- CVE JSON attachment regenerated: <comment URL>.

</details>
```

### Entry appended to the dropped tracker's rollup

```markdown
<details><summary><YYYY-MM-DD> · @<author-handle> · Merge (dropped) (into #<keep>)</summary>

**Closing as duplicate of [<tracker>#<keep>](https://github.com/<tracker>/issues/<keep>).** <one-sentence headline.>

Full content merged into [<tracker>#<keep>](https://github.com/<tracker>/issues/<N>) as *"Second independent report"*; <drop.reporter> credited alongside <keep.reporter> there.

All triage and advisory work continues on [#<keep>](https://github.com/<tracker>/issues/<N>).

<one-paragraph analysis matching the kept-side details>.

Specific artifacts merged: <CVSS scoring, attack chain, PoC, remediation options, etc.>.

See [the merge entry on <tracker>#<keep>](https://github.com/<tracker>/issues/<N>) for the full hand-off record.

<Reporter-notification line — one of the four canonical options from the sync skill.>

</details>
```

Both entries must render every cross-issue reference as a
clickable markdown link per the *Linking `<tracker>` issues and
PRs* convention in [`AGENTS.md`](../../../../AGENTS.md). No
six-line visible cap — the entire entry is already collapsed
inside `<details>`; write what the auditor needs. Do not pad.

---
