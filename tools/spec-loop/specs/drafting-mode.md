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
  issue-fix-workflow (experimental), and audit-finding-fix (experimental),
  in plugins/magpie-security/skills/issue-fix/,
  plugins/magpie-issue/skills/fix-workflow/ and
  plugins/magpie-repo-health/skills/audit-finding-fix/. Every PR they open
  passes through the shared pre-PR adversarial-review block
  (tools/dev/blocks/pre-pr-adversarial-review.md).
acceptance:
  - A drafting skill produces the failing test, the smallest production
    change, targeted test runs, and a commit — but never merges.
  - The PR is opened via `gh pr create --web` (human reviews in browser)
    or handed back for the human to push; no autopilot push/merge.
  - Security-class drafts scrub CVE / tracker-slug / "security fix" /
    "vulnerability" from every public surface until the embargo lifts.
  - Before a drafting skill opens a PR, the configured adversarial reviewers
    read the diff and the PR title and body as they will be posted; their
    findings are advisory and never block.
---

# Agentic Drafting mode

## What it does

The agent drafts a fix for a well-scoped problem — a triaged issue, a
CVE-allocated security report with team consensus on scope, a failing
test with an obvious cause, a documentation hole — and prepares a PR.
Every PR is reviewed and merged by a human committer; the agent never
merges its own work.

## Where it lives

- `security-issue-fix` (stable, security-only;
  `plugins/magpie-security/skills/issue-fix/`) — drafts the fix in the
  user's local `<upstream>` clone, runs local checks, opens the public
  PR via `gh pr create --web`, scrubs confidential framing.
- `issue-fix-workflow` (experimental;
  `plugins/magpie-issue/skills/fix-workflow/`) — drafts a fix for a triaged
  general-issue; **does not** open the PR on autopilot, hands back a
  branch + commits + test results.
  An optional Step 9 opens a draft PR with `gh pr create --web --draft`
  only when `--draft-pr` was passed and the user confirms after the
  hand-back.
- `audit-finding-fix` (experimental;
  `plugins/magpie-repo-health/skills/audit-finding-fix/`) — drafts a fix
  for a finding from an audit tool (ruff, mypy, security scanner); parses
  the finding report, implements the smallest fix, scope-checks the diff,
  and hands back a commit.
  An optional Step 8 opens a draft PR the same way, on `--draft-pr` and a
  confirmation.
- Other skills carry `mode: Drafting` and are specified with their own
  families: the release-management drafting skills
  ([release-management lifecycle](release-management-lifecycle.md)) and
  `security-model-prepare` / `security-model-update`
  ([security-model preparation](security-model-preparation.md)).
- `tools/dev` — shared local-check helpers, and
  `tools/dev/blocks/pre-pr-adversarial-review.md`, the shared block every
  PR-opening skill carries ([adversarial review](adversarial-review.md)).

## Behaviour & contract

- **Draft, never merge.** No skill in this mode merges. Opening the PR is
  `gh pr create --web` (human confirms in the browser) or a hand-back.
- **Confidentiality scrub** (security): commit message, branch name, PR
  title/body, newsfragment are scrubbed for CVE IDs, the tracker repo
  slug, and the words "security fix" / "vulnerability" before any write
  or push (see `AGENTS.md` § Confidentiality).
- **Adversarial review before the PR.** Each drafting skill that opens a
  PR carries the shared pre-PR block: once the title and body are final and
  after the skill's own public-surface checks (the security scrub
  included), the configured reviewers read only the diff and that public
  text.
  The security family runs the review whenever a reviewer is configured,
  whatever the `mode`; the others only on `mode: on-pr-create`.
  Findings are untrusted, advisory data; one the human wants fixed sends
  the flow back to the fix and its checks.
  `skill-and-tool-validate` fails a PR-opening skill without the block.
- **Commit trailer** follows the project's commit-attribution convention
  (`Generated-by:`, `Assisted-by:`, `Co-authored-by:`, none, or a custom
  trailer), resolved per `docs/setup/commit-attribution.md` and added with
  `git commit --trailer`; the agent-guard `commit-trailer` guard resolves it
  the same way (#1385).

## Out of scope

- Generic Agentic Drafting beyond the three shipped families (lint fixes at
  scale, doc holes at scale) — `proposed`, not yet built.
- Merging, releasing, or pushing without a human.

## Acceptance criteria

1. No drafting skill merges or force-pushes.
2. Security drafts pass the confidentiality scrub before any public write.
3. `skill-and-tool-validate` passes on the drafting-family skills,
   including the `pre-pr-review-block` check.

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
