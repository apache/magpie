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
  reviews" (overview.md § Substrate; projects/_template adopter config),
  but no skill turns that roster plus repository signal into an assignee
  suggestion. triage-mode.md § What it does ("propose routing to the
  right human") names the behaviour; no skill implements it yet.
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

- Skill (proposed, not implemented): `reviewer-routing` under
  `skills/`, in the Agentic Triage family alongside `pr-management-triage` and
  `issue-triage`.
- Roster source: the project's configured reviewer roster
  (`projects/<project>/` adopter config; `pmc-roster.md` for ASF
  projects, an arbitrary maintainer list for non-ASF adopters). The
  skill reads the roster through configuration, never a hard-coded list.
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

- **No skill is implemented yet.** This spec is `proposed`; the plan
  pass turns it into a single build item (one skill plus its eval suite).
- **Open-review-load signal is unspecified in detail.** Whether load is
  counted as open review requests, assigned-and-unreviewed PRs, or a
  decay-weighted recent count is left to the implementation; the contract
  only requires that some load signal is present and shown.
- **Non-ASF roster shape is unproven.** The roster-bounded contract
  assumes an adopter declares a maintainer list; no non-ASF profile
  fixture exercises routing yet (overlaps the non-ASF adopter profile
  work item in IMPLEMENTATION_PLAN).
