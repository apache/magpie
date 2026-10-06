<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Agentic Triage mode
status: experimental
kind: feature
mode: Triage
source: >
  MISSION.md § Technical scope (Triage). docs/modes.md § Triage
  (39 skills). Implemented by the pr-management, issue, security,
  contributor-growth, repo-health, and release-management skill
  families.
acceptance:
  - Every triage skill is read-only on tracker state or proposes-then-
    confirms; none transitions, closes, or labels without confirmation.
  - Classifications are grounded in prior triaged cases / the project's
    Security Model, not invented categories.
  - Security-side import/dedupe/sync/invalidate/allocate skills are
    stable; PR and general-issue triage are experimental.
---

# Agentic Triage mode

## What it does

The lowest-risk, foundational mode: spot inbound issues / security
reports / PRs, classify them, surface likely duplicates, link related
discussions, and propose routing to the right human. Every output is a
suggestion the human signs off on.

## Where it lives

- PR queue: `pr-management-triage`, `pr-management-stats`,
  `pr-management-code-review` (deep review is a triage variant),
  `pr-management-quick-merge` (read-only express-lane surfacing of
  trivial, low-risk PRs a maintainer can review in seconds),
  `pr-stale-sweep` (inactivity nudge or pre-close notice for PRs,
  skipping maintainer-court and ready-labelled PRs), and
  `reviewer-routing` (roster-bounded reviewer suggestion; see
  [reviewer-routing.md](reviewer-routing.md)).
  Reference implementation: `tools/pr-management-stats/`.
- General issues: `issue-triage`, `issue-reassess`, `issue-reproducer`,
  `issue-stale-sweep` (configurable inactivity sweep: nudge or
  propose-close after a warning window; waits for confirmation before
  posting), `issue-deduplicate` (merge two open issues describing the same
  root cause — proposes a close + cross-reference, waits for confirmation).
  Companion reporting skills: `issue-reassess-stats` (read-only dashboard
  over `verdict.json` files produced by `issue-reassess` campaigns) and
  `issue-backlog-stats` (read-only maintainer dashboard over the open
  general-issue backlog — health rating, age/staleness, area pressure,
  triage funnel).
- Contributor readiness (the `mode: Triage` members of the
  contributor-growth family; see
  [contributor-growth.md](contributor-growth.md)):
  `contributor-nomination` (read-only brief for a named contributor —
  activity breadth, consistency, and nomination-evidence prose for a
  committer or PMC thread);
  `contributor-activity-sweep` (read-only GitHub activity card for a
  named contributor over a configurable window);
  `contributor-calibrate` (threshold floors derived from past nomination
  decisions, behind the privacy-LLM gate; numbers-only config diff);
  `contributor-candidate-screen` (screens recent contributors against
  the floors and writes a per-candidate report to a verified-private
  repository);
  `contributor-identity-map` (GitHub handle to chat, mailing-list, and
  social identities, recording only maintainer-confirmed mappings);
  `contributor-sentiment` (sentiment-signal gate report for
  `experimental` to `stable` advancement).
  `committer-onboarding` (post-vote checklist) belongs to the same
  family but carries `mode: Meta`.
  Counting is deterministic through `tools/contributor-metrics`; chat
  evidence is read through `tools/chat` (`contract:chat`).
- Security inbound: `security-issue-import`, `-import-from-pr`,
  `-import-from-md`, `-import-from-scan` (triage-first scanner-output
  import via pluggable scan-format adapters),
  `-import-via-forwarder` (relay-broker variant: reports relayed by an
  upstream broker such as the ASF security team),
  `security-issue-triage` (batch-triage open tracker issues carrying
  `needs triage`), `security-issue-deduplicate`,
  `security-issue-invalidate`, `security-issue-sync`,
  `security-cve-allocate`, and `security-model-verify` (pre-flight on a
  published security model).
- Repo-health audits (see [repo-health-family.md](repo-health-family.md))
  and the four read-only `release-*` skills (`release-verify-rc`,
  `release-vote-tally`, `release-archive-sweep`,
  `release-audit-report`; see
  [release-management-lifecycle.md](release-management-lifecycle.md))
  are also catalogued under Triage in `docs/modes.md`.
- Adapters it reads through: `tools/github`, `tools/jira`,
  `tools/ponymail`, `tools/gmail`, `tools/mail-source`,
  `tools/contributor-metrics`, `tools/chat`.

## Behaviour & contract

- **Read-only or propose-then-confirm.** `issue-triage` and
  `security-issue-triage` post a *proposal comment* on confirmation and
  never flip labels, close, or allocate. Reproducers produce evidence
  (`verdict.json`), never post.
- Six-class disposition vocabulary on the security side
  (`VALID` / `DEFENSE-IN-DEPTH` / `INFO-ONLY` / `INVALID` /
  `PROBABLE-DUP` / `FIX-ALREADY-PUBLIC`).
- Duplicate detection keys on stable identifiers (Gmail `threadId`,
  GHSA-ID), not on fuzzy body text alone.

## Out of scope

- Authoring fixes (that is Agentic Drafting, [Drafting](drafting-mode.md)).
- Any state change a human has not confirmed in-session.

## Acceptance criteria

1. No triage skill performs an unconfirmed state change.
2. `skill-and-tool-validate` passes on all triage-family skills.
3. docs/modes.md Agentic Triage table matches the shipped skill set.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- PR and general-issue triage are `experimental` — no adopter-pilot eval
  has run; behaviour may change.
- **General-issue triage gained its deduplication skill and backlog
  dashboard.** `issue-deduplicate` (general-issue dedup, parallel to
  `security-issue-deduplicate`) and `issue-backlog-stats` (open-issue
  backlog dashboard, parallel to `pr-management-stats`) have now shipped
  (`experimental`); `issue-stale-sweep` provides stale-handling /
  close-proposal. No adopter-pilot eval has run on the general-issue
  family yet, so behaviour may change.
- **The contributor-growth skills are now a named family.** They ship
  as the `magpie-contributor-growth` plugin (with three Mentoring
  members in `magpie-mentoring`) and have their own spec,
  [contributor-growth.md](contributor-growth.md), which tracks the
  remaining gaps: PMC-member nomination (distinct from committer),
  emeritus / inactive-committer handling, and contributor offboarding.
- **Repo-health audits are now a six-skill family — feature-complete.**
  `ci-runner-audit`, `workflow-security-audit` (zizmor-backed),
  `dependency-audit`, `license-compliance-audit`, `flaky-test-triage`, and
  `dependency-license-audit` have all shipped (read-only, `experimental`); see
  [repo-health-family.md](repo-health-family.md). No candidates remain.
