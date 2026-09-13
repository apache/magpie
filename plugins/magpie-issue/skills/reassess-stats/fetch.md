<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Fetch — reading the verdict files

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 1:
discovering and parsing the `verdict.json` files in a campaign
directory.

## Directory walk

Given a campaign directory `<campaign-dir>`, find every file
matching:

```text
<campaign-dir>/<KEY>/verdict.json
```

Where `<KEY>` is a tracker key (typically `[A-Z][A-Z0-9_]*-\d+`
for JIRA-style trackers, or `<owner>-<repo>-<N>` for GitHub-Issues-
style). The directory layout convention is in
[`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md).

Skip subdirectories that don't match the expected pattern (the
directory may also contain `report.md`, `_template/`, or other
scaffolding).

## Schema validation

Parse each `verdict.json` against the schema in
[`issue-reproducer/verdict-composition.md`](../reproducer/verdict-composition.md).
Required fields:

- `key`, `shape`, `classification`, `nature`, `rev`, `jdk`,
  `command`, `exit_code`, `matched_original_failure`.
- Optional fields with strict shapes when present: `cases`,
  `cases_summary`, `cross_type_probe`, `operator_variants_probe`,
  `runtime_ms`, `notes`.

A file that:

- Doesn't exist → silent skip (the campaign loop wrote no verdict
  for that candidate yet).
- Exists but doesn't parse → record as a parse error; surface in
  the dashboard's *"limitations"* section; **do not** aggregate
  into totals.
- Parses but has an unknown `classification` or `nature` value →
  record as a schema-error; surface; do not aggregate.

Per Golden rule 4 in [`SKILL.md`](SKILL.md), the skill does **not**
invent values to fill in missing fields. A partial verdict is a
parse error.

## Auxiliary artefacts

For each successfully-parsed `verdict.json`, also detect the
presence of auxiliary artefacts in the same `<campaign-dir>/<KEY>/`
directory:

| File | Used for |
|---|---|
| `description.md` | Issue body excerpt; the dashboard's per-issue drill-in surfaces the title |
| `original.<ext>` | Verbatim reporter's code; the dashboard's drill-in offers a "view source" link |
| `reproducer.<ext>` | Adapted runnable form |
| `run.log` | Captured run output |
| `cross-type-probe.<ext>` + `cross-type-probe.log` | Probe artefacts; the dashboard's new-issue-candidates section references these |
| `operator-variants-probe.<ext>` + `operator-variants-probe.log` | Same for operator-variant probes |

Absence of any of these is fine; the dashboard renders whatever it
finds.

## Title extraction (best-effort)

The verdict carries `key` but not the issue title. For the
dashboard's display, extract the title from `description.md` if
present (typically the first `#` heading line). Fall back to the
key alone if the title isn't extractable.

This is a presentation nicety; the skill does not fetch from
`<issue-tracker>` to enrich titles (Golden rule 1 — no network).

## Multi-campaign discovery

When the user supplies a path that contains multiple campaign
subdirectories (e.g., `<scratch>/` itself), the fetch detects each
campaign by looking for a `report.md` or at least one `<KEY>/
verdict.json` pattern. The skill surfaces each detected campaign
and asks the user to pick — see Golden rule 5 in
[`SKILL.md`](SKILL.md).

## Output

Return to the orchestrator:

- A list of `(key, verdict, aux_artefacts)` tuples, one per
  successfully-parsed candidate.
- A list of `(path, error_message)` tuples for parse failures.
- The campaign directory's `report.md` content if present (used
  by [`render.md`](render.md) for the *"about this campaign"*
  panel).

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration.
- [`classify.md`](classify.md) — what happens after fetch.
- [`issue-reproducer/verdict-composition.md`](../reproducer/verdict-composition.md) —
  the schema being validated.
- [`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md) —
  campaign directory layout.
