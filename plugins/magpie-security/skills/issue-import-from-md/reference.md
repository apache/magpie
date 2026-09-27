<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — scope limits and failure modes

## What this skill does **not** do

- **Does not run the validity discussion.** Every finding lands as
  `Needs triage`; Step 3 of the handling process happens in tracker
  comments after import.
- **Does not draft a reporter reply.** There is no reporter — the
  markdown file is the report, and any clarification questions the
  team has about a finding are recorded as comments on the
  resulting tracker, not on a Gmail thread.
- **Does not allocate CVEs.** A finding tagged `**Severity:** HIGH`
  in the source markdown is *still* unassessed from the security
  team's perspective; the CVE-allocation gate (per
  [`security-cve-allocate`](../cve-allocate/SKILL.md)) requires the team's
  own validity decision first.
- **Does not parse markdown formats other than the one documented
  in Step 1.** If the input file uses a different shape (e.g.
  `### Title` instead of `# Title`, or a YAML front-matter block
  instead of `**Field:**` lines), surface a one-line ask for the
  user to either reformat the file or open the trackers manually.
  The skill must not silently best-effort parse a divergent shape;
  the resulting trackers would be subtly malformed and confuse the
  rest of the lifecycle.
- **Does not characterise the source as authoritative.** The
  status-rollup line `Severity (from source): HIGH (informational;
  CVSS scoring happens at allocation)` is the standard wording —
  the source's tags are recorded, not adopted.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| File parse yields zero findings | The file uses a different heading level or no `**Severity:**` metadata block | Stop; surface the expected shape from Step 1 and ask the user to reformat. |
| `gh api repos/<tracker>/issues` returns 422 | Title or body field shape doesn't match the issue template | Re-check the body against the eleven `### <field>` headings; the heading text is case-sensitive. |
| `addProjectV2ItemById` returns `not found` for the project | Project-board node ID changed in `<project-config>/project.md` | Re-run the introspection query in [`project-board.md`](../../../../tools/github/project-board.md) and update `<project-config>/project.md`. |
| Many possible-duplicate hits surfaced for every finding | The file is a re-scan against an already-triaged branch | Pause; consider whether the right action is `skip` for every finding (the existing trackers cover this) rather than landing duplicates. |
| `gh api` rate-limits mid-batch | Large file (50+ findings) hits the per-minute limit | The skill surfaces the partial-success recap from Step 6; re-invoke against the same file later for the failed indices (the duplicate-guard at Step 2 will catch the already-imported ones). |
