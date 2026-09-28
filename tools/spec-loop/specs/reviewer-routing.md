<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Reviewer routing
status: experimental
kind: feature
mode: Triage
source: >
  MISSION.md § Rationale ("review-cycle latency" is one of the two named
  priorities) and § Technical scope (Agentic Triage: "proposes initial routing",
  "proposes routing"). The substrate config already declares "who
  reviews" (overview.md § Substrate; plugins/magpie-setup/templates adopter config),
  but no skill turns that roster plus repository signal into an assignee
  suggestion. triage-mode.md § What it does ("propose routing to the
  right human") names the behaviour. Skill ships experimental in
  plugins/magpie-pr-management/skills/reviewer-routing/ with an eval
  suite under tools/skill-evals/evals/reviewer-routing/.
acceptance:
  - The skill is read-only on tracker state and proposes-then-confirms;
    it never assigns, requests review, or labels without confirmation.
  - The suggested reviewer is drawn from the project's configured roster
    only; the skill never invents a handle or routes to a non-member.
  - Every suggestion carries its reasoning (touched paths, prior-art
    PRs, current open-review load) so the maintainer can audit the call.
---

# Reviewer routing

## What it does

Proposes which maintainer an inbound issue or PR should go to. The two
complaints MISSION names loudest are onboarding latency and review-cycle
latency; routing attacks the second directly by removing the "who should
look at this?" pause that stalls a fresh PR before any review begins.

Given an open issue or PR, the skill scores the configured reviewer
roster and proposes a primary reviewer (and optionally a backup),
grounding each suggestion in three signals: roster eligibility for the
touched area, git-history familiarity with the changed paths, and the
reviewer's current open-review load so routing spreads work instead of
piling it on the most-recently-active person. The output is a proposal a
maintainer confirms; nothing is assigned on autopilot. This is the
Agentic Triage-mode counterpart to `contributor-nomination` on the read-only
side: a grounded brief a human acts on, not a state change.

## Where it lives

- Skill: `plugins/magpie-pr-management/skills/reviewer-routing/SKILL.md`,
  shipped in the `magpie-pr-management` plugin and reachable through the
  `skills/reviewer-routing` and `.agents/skills/magpie-reviewer-routing`
  symlinks. Agentic Triage mode, alongside `pr-management-triage` and
  `issue-triage`. Eval suite under `tools/skill-evals/evals/reviewer-routing/`.
- Roster source: the project's configured reviewer roster, read through
  configuration, never a hard-coded list.
  ASF projects use `<project-config>/release-trains.md` (the
  per-component handle table `issue-triage` and `pr-management-triage`
  already read); non-ASF adopters use `<project-config>/reviewer-roster.md`
  (GitHub handles and declared areas, optional per-reviewer
  `max_reviews`). Scaffolds for both live in
  `plugins/magpie-setup/templates/` (`projects/_template` is a symlink
  to it); `projects/non-asf-example/reviewer-roster.md` is a worked
  non-ASF example.
- Privacy-LLM gate: `<project-config>/privacy-llm.md`, checked with
  `tools/privacy-llm/checker` at Step 0.
- Repository signal: `tools/github` for changed paths, blame/history on
  those paths, and the reviewer's current open-review queue.
- Identity resolution for ASF projects: `tools/apache-projects`
  (committee roster, Apache IDs), reused exactly as the security and
  contributor skills resolve handles.
- Adapters it reads through: `tools/github`; `tools/apache-projects`
  where ASF roster context applies.

## Behaviour & contract

- **Read-only, propose-then-confirm.** The skill emits a routing
  proposal; the maintainer assigns / requests review as themselves. No
  skill call sets an assignee, requests a review, or applies a label
  without in-session confirmation.
- **Roster-bounded.** Suggestions come only from the configured roster.
  An empty or unresolved roster yields `NO ELIGIBLE REVIEWER, needs
  maintainer call` rather than a guessed handle, mirroring the
  conservative-tally refusal in `release-vote-tally`.
- **Reasoned, auditable output.** Each suggestion lists the signals
  behind it (matched area / touched paths, the prior-art PRs that touched
  the same paths, the reviewer's current open-review count). A maintainer
  can see why a name surfaced and overrule it.
- **Load-aware, not just expertise-aware.** Scoring weighs current
  open-review load so routing does not concentrate every PR on the
  single most expert reviewer; the contract is to surface a workable
  human, not the theoretically optimal one.
- **Untrusted content stays data.** Issue / PR bodies are input data,
  never instructions; an injected "assign this to X" line in a PR
  description is ignored, the same posture every triage skill inherits.
  When one is detected, the proposal says it is based on metadata and
  roster signals only.
- **Privacy gate before any body is fetched.** Step 0 checks `gh`
  authentication, reads `project.md`, resolves the roster and the input,
  then runs `privacy-llm-check` (flags: `--config`,
  `--reads-private-list`, `--quiet`); a non-zero exit is a hard stop.
  Step 0 returns a JSON verdict (`proceed` / `blocked`) with
  `privacy_gate_passed` and `roster_source`
  (`release-trains` / `reviewer-roster` / `null`).
- **Deterministic scoring.** Area match scores 3 points per matched area
  (capped at 6), git familiarity 2 points per authored path in the
  changed set (capped at 6; zero for issues), and load subtracts 1 point
  per open review request above 2 (down to -5). Load is the count of
  open PRs on `<upstream>` with a review requested from the member; at
  or above `max_reviews` (default 5) the member is `OVERLOADED`.
  An overloaded member never takes the primary slot but may be proposed
  as backup when no one else remains. Ties break alphabetically.
  If every member is overloaded or none matches the touched areas, the
  output is `NO ELIGIBLE REVIEWER — all roster members overloaded or no
  area match`.
- **Maintainer controls the outcome.** The confirmation step accepts
  the proposal, declines it, swaps primary and backup, or overrides the
  primary with a handle that must itself be on the roster.
  On accept the skill prints the `gh` command for the maintainer to run
  and stops; it never runs it.

## Out of scope

- Assigning, requesting review, or labelling on the tracker (those are
  human acts the maintainer performs after confirming).
- Authoring or merging the change (Agentic Drafting / Agentic Autonomous, not Agentic Triage).
- Inventing a reviewer outside the roster, or routing on contributor
  sentiment / performance ranking — the skill proposes who is best
  placed to review a specific change, not who is a "better" maintainer.

## Acceptance criteria

1. `reviewer-routing` performs no unconfirmed tracker state change.
2. Every suggested reviewer is a member of the configured roster; an
   unresolved roster produces an explicit `NO ELIGIBLE REVIEWER` signal,
   never a fabricated handle.
3. Each suggestion carries its grounding signals (touched paths,
   prior-art PRs, open-review load).
4. The skill validates under `skill-and-tool-validate` and ships an eval
   suite under `tools/skill-evals/evals/reviewer-routing/`, including an
   adversarial case asserting an injected "assign to X" line is ignored.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/reviewer-routing/
```

## Known gaps

- **Open-review-load signal is now defined.** The skill counts open
  review requests (`review-requested:@<handle>` on open PRs) against a
  per-reviewer `max_reviews` (default 5); assigned-but-unrequested PRs
  and recency decay are not counted. Gap cleared; a richer load model
  would be a future change.
- **The skill names a checker flag that does not exist.** Step 0 of
  `SKILL.md` tells the maintainer to "run `privacy-llm-check --list`"
  after a gate failure, but `tools/privacy-llm/checker` accepts only
  `--config`, `--reads-private-list` and `--quiet`, so that command
  fails with an argument error. The skill text needs correcting.
- **Non-ASF roster shape is now exercised.** `projects/non-asf-example/reviewer-roster.md`
  provides a Velox Stream roster with no ASF-specific fields; the
  `non-asf-profile-smoke/step-reviewer-routing/` eval suite asserts that
  area-match routing selects a primary reviewer and that a no-area-match case
  returns `NO ELIGIBLE REVIEWER` without proposing a fallback under the
  `organization: independent` profile. Gap cleared.
- **`experimental` — no adopter pilot has run.** The skill ships but no
  end-to-end routing workflow has been exercised in a live maintainer
  session; signal weights and roster-match heuristics may change.
- **Row present in `docs/modes.md` Triage table.** The row was added in
  #701; the Privacy-LLM gate preflight (Step 0) landed separately in #731.
  The skill remains at `mode: Triage` and `experimental`.
