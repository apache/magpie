<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Golden rule details

Companion to [`SKILL.md`](SKILL.md). Full body text of Golden rules 1–8; SKILL.md keeps each rule's title with a pointer here.

## Golden rule 1 — no mutations, ever

This skill only reads. It must
not post comments, add labels, close, or assign anything. If the
maintainer asks for stats and also wants an action, redirect to
`issue-triage`, `issue-stale-sweep`, or `issue-fix-workflow`.

## Golden rule 2 — reuse `issue-stale-sweep`'s staleness definition

The staleness panel and stale-candidate hero card depend on the same
`warn_days` / `close_days` thresholds and the same last-activity logic
(`updated_at` / last-comment timestamp) that `issue-stale-sweep` uses.
Both skills must agree on "is this issue stale".

## Golden rule 3 — one query per batch, not per issue

Fetch the
entire open-issue list in paginated batches. Never call a per-issue
detail API inside the main loop; use the fields available in the list
query.

## Golden rule 4 — include a legend with every render

Column
abbreviations and colour codes in the detailed table and area panel
must have a printed legend. The hero cards and recommendation panel are
self-explanatory and don't need one.

## Golden rule 5 — state the input scope up front

Before rendering,
print one line summarising what the stats cover: tracker name, total
open issue count, cutoff date for closed-this-week, and viewer login.

## Golden rule 6 — recommendations are deterministic, not opinions

Every action surfaced in the "What needs attention" panel comes from a
fixed rule table. The skill never editorialises. New rules are added by
updating the rules table, not by inserting free-text.

## Golden rule 7 — screen for security signals, never expose them

If a title or label contains signals suggesting a security vulnerability
(CVE, RCE, "auth bypass", "injection"), exclude the issue from the
aggregate counts and surface a one-line privacy notice: *"N issues
excluded from stats: may contain security signals — route privately."*
Do not include issue titles or identifiers in that notice.

## Golden rule 8 — render ALL sections, never silently skip

If a
section's data is genuinely unavailable (e.g., no area labels on any
issue), render a one-line stub explaining why — never omit a section.
