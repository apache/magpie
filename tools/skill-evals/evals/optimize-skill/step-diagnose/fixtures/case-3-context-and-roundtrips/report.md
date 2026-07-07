<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: .claude/skills/security-issue-sync/SKILL.md

wc -l SKILL.md: 460
Largest section: "## Step 4 — Apply" (44 lines) — within range.

Placeholder linter: clean.
In-context reads: Step 2 pulls the entire issue body into the agent context to update one `### Affected versions` field — the rest of the body is loaded for no analytical reason.
Per-item fetch loop: Step 1 fetches each linked PR one at a time in a loop over the candidate set; a single upfront batch would return them all.
Pre-flight filter: present.
