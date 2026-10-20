<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-deduplicate — merged body and rollup entries

`<sm>` is the `security-management issue-deduplicate` command of [`SKILL.md`](SKILL.md#prerequisites).

## Step 3 — Build the merged body proposal

The output is a single body that preserves both reporters' content verbatim.
The body-field schema (role names, empty-field convention, body-field-surgery pattern) is in
[`tools/github/issue-template.md`](../../../../tools/github/issue-template.md);
the adopting project's concrete field names live in
[`<project-config>/project.md`](../../../../<project-config>/project.md#issue-template-fields).

**What you write.** Two pieces of your own, and two merged values only when the trackers disagree:

- `headline` — one sentence for the visible line above the collapsed report: same root-cause bug, different attack vector or affected process.
- `analysis` — one paragraph of WHY the two reports are the same root-cause bug (same function, same file, same fix)
  while describing different attack vectors, affected processes or threat-model boundaries.
  It is written for a future triager, so make it read naturally months after the duplicate was closed.
- `merged_summary` — only when both *Short public summary* fields are populated and differ: one summary covering both vectors explicitly (the release manager refines it at Step 13).
- `affected_versions` — only when both *Affected versions* differ: the broader range, the lower `version` bound and the higher `lessThan` bound of the two.
- `cwe` — only after the user resolved a CWE conflict: the CWE they picked.

Write `{tracker, date, headline, analysis, keep, drop, merged_summary, affected_versions, cwe, body_fields}` — each side `{number, body, created}` from Step 1 — and run `<sm> merge-body`.
It rewrites the kept body one field at a time with github-body-field's `replace_field`,
which refuses any rewrite that would change another field, so the CVE JSON attachment, a project's extra fields and every unchanged value stay byte-exact:

- *The issue description*: the kept report as it is, then **Second independent report: `<drop link>` — merged on `<date>`.** with your headline,
  over a collapsed `<details>` (*Full report from `<drop reporter>`*) holding your analysis and the dropped report **verbatim** —
  except that reporter-supplied CVSS vectors, scores and severity labels are removed (`scores_removed`),
  a line that would end a field or carries a machine marker gains a leading `\`, and an unmatched `</details>` is escaped so the disclosure cannot close early.
  A chain merge (the dropped report already holding its own *Second independent report* block) stays nested, never flattened.
- *Reporter credited as*, *Security mailing list thread*, *PR with the fix*: both sides, one line each, verbatim — the merge never re-synthesises a credit; threads earliest report first.
- *Short public summary*, *Affected versions*: the one populated side, or your merged value; both populated and different without one is refused.
- *CWE*: the one populated side; two different CWEs are a blocker (`blockers`) until the user picks one.
- *Severity*, *CVE tool link*, *Public advisory URL*: the kept side's. A reporter-supplied severity on the dropped side is never carried over (`severity_note`), per the independent-scoring rule in [`AGENTS.md`](../../../../AGENTS.md).

A field value the dropped side would add that holds an HTML comment (`<!--`) is refused rather than escaped:
machine markers (the CVE-JSON attachment, rollup and sync markers) never travel in copied field text, and a backslash in a credit or link would be visible noise.
Ask the user to clean that field on the dropped tracker by hand, then run the merge again.

**The [bot/AI credit policy](../../../../tools/cve-tool-vulnogram/bot-credits-policy.md)** applies when consolidating.
A finder-side credit matching the bot rule stays in *Reporter credited as* and is listed in `tool_credits`; the CVE JSON generator emits it with `type: "tool"`.
Surface each in the proposal as *"credited as tool (during merge): `<line>` (matches bot policy)"* with its source tracker,
and, when the dropped tracker has an inbound reporter thread, propose the policy's *clarification-reply* draft asking whether a human behind the handle should be **additionally** credited as finder.
A bot-matching *Remediation developer* on the dropped side is skipped (`skipped_credits`; the policy has no tool mapping there): surface it as *"skipped credit (during merge): `<line>`"*.
The user can override per the policy doc.

The **Second independent report** block is the load-bearing part of the merge:
every future triager reads both reports in one place, without chasing the closed duplicate's content.

## Step 4 — Build the rollup-entry proposals

Two rollup-comment entries, one per tracker — **not** two new top-level comments —
appended to each tracker's existing status-rollup comment via the upsert recipe in
[`tools/github/status-rollup.md`](../../../../tools/github/status-rollup.md#upsert-recipe--append-to-an-existing-rollup-or-create-one).
When either tracker has no rollup yet (legacy tracker pre-dating the convention),
the append creates one, and Step 5 folds any pre-existing legacy bot comments in first.

Write `{tracker, keep, drop, cve_id, record_url_template, retract_cve, headline, analysis, next_step, notification, field_changes, blockers, artifacts}` —
each side `{number, credit, thread}` — and run `<sm> render-rollup-kept` and `<sm> render-rollup-dropped`.
Each prints the entry body and its action label (`Merge (kept) (from #<drop>)`, `Merge (dropped) (into #<keep>)`); the Step 5 call writes the
`<details><summary>YYYY-MM-DD · @user · <Action></summary>` envelope.

- The kept entry links the dropped tracker, lists both credits and both threads, the CVE that stays allocated here (and the dropped side's being retracted),
  the **Next:** step, the *Reporter notification* line, your analysis, the per-field hand-off (`field_changes`: *field* and its before → after) and every blocker.
- The dropped entry links the kept tracker, says the content was merged there as *"Second independent report"* with both reporters credited,
  points all further work at the kept tracker, and carries your analysis and the merged artifacts (CVSS scoring, attack chain, PoC, remediation options).

The *Reporter notification* line is one of the four canonical options of the sync skill (`notification`: `notified`, `team_member`, `draft_pending` with a draft ID checked to be still in Drafts, or `omitted`).
Every line starts at column 0 and every cross-tracker reference is a link; `bare_refs` must be empty.
There is no six-line visible cap: the entire entry is already collapsed inside `<details>`, so write what the auditor needs. Do not pad.

---
