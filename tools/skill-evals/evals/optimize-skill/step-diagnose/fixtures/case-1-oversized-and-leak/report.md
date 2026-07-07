<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: .claude/skills/security-issue-import/SKILL.md

wc -l SKILL.md: 1842
Largest sections: "## Step 2 — …" (410 lines), "## Step 4 — …" (388 lines) — both self-contained.

Placeholder linter: 2 hits in the body outside `example:` markers — a concrete `<upstream>` repo slug and a literal mailing-list address baked into Step 3 prose (should resolve from `<project-config>`).

In-context reads: none — the skill already routes body edits through github-body-field.
Per-item fetch loop: none — Step 1 already fetches the candidate set in one upfront query.
Pre-flight filter: present — a deterministic classifier already drops idle candidates.
