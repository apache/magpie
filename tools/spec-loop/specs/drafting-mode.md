<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Agentic Drafting mode
status: experimental
kind: feature
mode: Drafting
source: >
  MISSION.md § Technical scope (Drafting). docs/modes.md § Drafting.
  Implemented by security-issue-fix (stable, security-only),
  issue-fix-workflow (experimental), and audit-finding-fix (experimental).
acceptance:
  - A drafting skill produces the failing test, the smallest production
    change, targeted test runs, and a commit — but never merges.
  - The PR is opened via `gh pr create --web` (human reviews in browser)
    or handed back for the human to push; no autopilot push/merge.
  - Security-class drafts scrub CVE / tracker-slug / "security fix" /
    "vulnerability" from every public surface until the embargo lifts.
---

# Agentic Drafting mode

## What it does

The agent drafts a fix for a well-scoped problem — a triaged issue, a
CVE-allocated security report with team consensus on scope, a failing
test with an obvious cause, a documentation hole — and prepares a PR.
Every PR is reviewed and merged by a human committer; the agent never
merges its own work.

## Where it lives

- `security-issue-fix` (stable, security-only) — drafts the fix in the
  user's local `<upstream>` clone, runs local checks, opens the public
  PR via `gh pr create --web`, scrubs confidential framing.
- `issue-fix-workflow` (experimental) — drafts a fix for a triaged
  general-issue; **does not** open the PR on autopilot, hands back a
  branch + commits + test results for the human to push.
- `audit-finding-fix` (experimental) — drafts a fix for a finding from
  an audit tool (ruff, mypy, security scanner); parses the finding
  report, implements the smallest fix, scope-checks the diff, and hands
  back a commit for the human to push.
- `tools/dev` — shared local-check helpers.

## Behaviour & contract

- **Draft, never merge.** No skill in this mode merges. Opening the PR is
  `gh pr create --web` (human confirms in the browser) or a hand-back.
- **Confidentiality scrub** (security): commit message, branch name, PR
  title/body, newsfragment are scrubbed for CVE IDs, the tracker repo
  slug, and the words "security fix" / "vulnerability" before any write
  or push (see `AGENTS.md` § Confidentiality).
- **Commit trailer** `Generated-by:` — never `Co-Authored-By:` an agent.

## Out of scope

- Generic Agentic Drafting beyond the three shipped families (lint fixes at
  scale, doc holes at scale) — `proposed`, not yet built.
- Merging, releasing, or pushing without a human.

## Acceptance criteria

1. No drafting skill merges or force-pushes.
2. Security drafts pass the confidentiality scrub before any public write.
3. `skill-and-tool-validate` passes on the drafting-family skills.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- Three drafting skills are now shipped: `security-issue-fix` (stable),
  `issue-fix-workflow` (experimental), and `audit-finding-fix`
  (experimental). The remaining `proposed` surface is generic drafting at
  scale (lint-fix batches, doc-hole sweeps) — not yet planned.
- No drafting skill covers doc-hole or large-scale lint-fix batch work;
  those remain out of scope until a family spec is written.
