<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — scope limits and failure modes

## What this skill does **not** do

- **Does not run the validity discussion.** Every finding lands as
  `Needs triage`; Step 3 of the handling process happens in tracker
  comments after import.
- **Does not draft a reporter reply.** There is no reporter — the file is the report;
  clarification questions go in comments on the resulting tracker.
- **Does not allocate CVEs.** A `**Severity:** HIGH` finding is *still* unassessed;
  [`security-cve-allocate`](../cve-allocate/SKILL.md) needs the team's own validity decision first.
- **Does not parse markdown formats other than the one documented in Step 1.**
  For a different shape (e.g. `### Title` instead of `# Title`, or YAML front matter instead of `**Field:**` lines), ask the user in one line to reformat the file or open the trackers manually.
  Never best-effort parse a divergent shape — the trackers would be subtly malformed.
- **Does not characterise the source as authoritative.** The rollup line `Severity (from source): HIGH (informational;
  CVSS scoring happens at allocation)` records the source's tags without adopting them.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| File parse yields zero findings | The file uses a different heading level or no `**Severity:**` metadata block | Stop; surface the expected shape from Step 1 and ask the user to reformat. |
| `gh api repos/<tracker>/issues` returns 422 | Title or body field shape doesn't match the issue template | Re-check the body against the eleven `### <field>` headings; the heading text is case-sensitive. |
| `addProjectV2ItemById` returns `not found` for the project | Project-board node ID changed in `<project-config>/project.md` | Re-run the introspection query in [`project-board.md`](../../../../tools/github/project-board.md) and update `<project-config>/project.md`. |
| Many possible-duplicate hits surfaced for every finding | The file is a re-scan against an already-triaged branch | Pause; consider whether the right action is `skip` for every finding (the existing trackers cover this) rather than landing duplicates. |
| `gh api` rate-limits mid-batch | Large file (50+ findings) hits the per-minute limit | The skill surfaces the partial-success recap from Step 6; re-invoke against the same file later for the failed indices (the duplicate-guard at Step 2 will catch the already-imported ones). |
