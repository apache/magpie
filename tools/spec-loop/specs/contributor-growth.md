<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Contributor-growth family
status: experimental
kind: feature
mode: Triage
source: >
  MISSION.md § Rationale ("Project health depends on a growing contributor
  base"). triage-mode.md § Known gaps (contributor-growth skills span
  Agentic Triage and Agentic Mentoring but are not yet a named family).
  mentoring-mode.md § Known gaps. Implemented by contributor-nomination,
  contributor-activity-sweep, committer-onboarding, good-first-issue-author,
  and mentoring-welcome.
acceptance:
  - Every family skill is read-only or propose-before-post; none
    transitions, promotes, or announces without explicit maintainer
    confirmation.
  - The contributor-to-committer path has at least one skill per stage:
    first contact, activity tracking, nomination brief, post-vote onboarding.
  - All family skills validate under skill-and-tool-validate with no
    errors.
---

# Contributor-growth family

## What it does

Groups the skills that span the contributor-to-committer (and
committer-to-PMC) path into a named family. Each skill covers one
stage a maintainer or nominator cares about:

1. **First contact** — welcoming a first-time contributor to lower
   onboarding latency.
2. **Activity tracking** — surfacing a contributor's sustained
   work in a form useful to the nomination thread.
3. **Nomination brief** — assembling the evidence prose a PMC uses
   to open a committer or PMC vote thread.
4. **Good first issue authoring** — keeping the on-ramp stocked with
   newcomer-ready issues so contributors can find self-contained tasks.
5. **Post-vote onboarding** — walking the nominator through the
   ICLA check, account provisioning, permissions, and welcome
   announcement once a vote passes.

Each skill is read-only on governance artefacts (GitHub collaborator
list, `author_association` field, ICLA records) and proposes every
state change for human sign-off.

## Where it lives

- Skill: `mentoring-welcome` — drafts a first-contact orientation
  comment for a first-time contributor on a newly opened issue or PR.
  Detects first-time authorship via the GitHub `author_association`
  field; skips repeat contributors; proposes the comment and does not
  post without maintainer confirmation. Ships `mode: Mentoring`
  + `experimental`, eval suite under
  `tools/skill-evals/evals/mentoring-welcome/`.
- Skill: `contributor-activity-sweep` — read-only GitHub activity
  card for a named contributor: PR authorship, code-review
  participation, issues, and comments over a configurable window.
  Ships `mode: Triage` + `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-activity-sweep/`.
- Skill: `contributor-nomination` — nomination-readiness brief for a
  named contributor: activity breadth, consistency, vendor-neutrality
  context, and evidence prose for a committer or PMC thread.
  Read-only; never posts to any list. Ships `mode: Triage`
  + `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-nomination/`.
- Skill: `good-first-issue-author` — drafts one net-new good first
  issue from a supplied gap or small task; suitability gate plus
  R1–R9 readiness checklist; waits for maintainer confirmation
  before filing via `gh`. Ships `mode: Mentoring` + `experimental`,
  eval suite under `tools/skill-evals/evals/good-first-issue-author/`.
- Skill: `committer-onboarding` — post-vote ICLA check, account
  provisioning, permissions, and welcome-announcement checklist for
  committer and PMC promotions at ASF TLPs and podlings.
  Propose-before-post at every state-changing step. Ships
  `mode: Triage` + `experimental`, eval suite under
  `tools/skill-evals/evals/committer-onboarding/`.

## Behaviour & contract

- **Read-only or propose-then-confirm.** Skills read GitHub
  collaborator lists, `author_association` fields, and public
  activity histories; they never write a comment, post an
  announcement, or modify a roster without explicit maintainer
  confirmation.
- **Governance steps are paste-ready recipes, not autopilot.**
  `committer-onboarding` emits commands and draft announcements the
  nominator executes as themselves; the skill never submits an ICLA
  request, invites an account, or modifies repository permissions
  directly.
- **Evidence is curated, not fabricated.** `contributor-nomination`
  and `contributor-activity-sweep` read public GitHub activity only;
  they do not invent contributions or inflate counts. The brief and
  activity card are inputs for a PMC vote, not a pre-decided
  recommendation.
- **Teaching register for first-contact.** `mentoring-welcome` and
  `good-first-issue-author` follow the Agentic Mentoring mode's tone
  contract (polite, never gatekeeping) and hand off to a human
  reviewer on anything that exceeds the agent's scope.

## Out of scope

- **PMC-member nomination** (distinct from committer-to-PMC path):
  not yet specced; the vote mechanics, quorum rules, and post-vote
  steps differ enough to warrant a separate spec-RFC pass that
  enumerates the option set and per-project policy knobs.
- **Emeritus / inactive-committer handling and contributor
  offboarding**: intentionally deferred pending scope agreement —
  these involve project-level governance decisions (roster policy,
  communication norms) that no skill can safely generalise without
  per-project configuration.
- Auto-promoting a contributor: all promotion decisions stay with the
  PMC; the skills prepare evidence and checklists, never act on the
  vote outcome without the nominator's explicit direction.
- Backlog curation (relabeling the existing issue backlog as good
  first issue candidates): `good-first-issue-author` drafts net-new
  issues only; backlog curation is a separate capability not yet
  specced.

## Acceptance criteria

1. `mentoring-welcome` does not draft or post for repeat contributors
   (the `author_association` gate fires before any draft is produced).
2. `contributor-nomination` and `contributor-activity-sweep` are
   read-only — neither posts, labels, nor modifies any issue or PR.
3. `committer-onboarding` emits paste-ready command recipes; no step
   submits ICLA forms or changes repository permissions without the
   nominator's direct action.
4. All family skills pass `skill-and-tool-validate` with no errors.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **PMC-member nomination is not yet specced.** The committer-to-PMC
  promotion has different vote mechanics (full-PMC vote, different
  quorum) and post-vote steps from committer promotion. Defining it as
  a capability-flag variant of `committer-onboarding` or as a
  standalone skill requires a spec-RFC pass that enumerates the option
  set and documents defaults. Candidate work item for a future plan
  pass.
- **Emeritus / inactive-committer handling and contributor offboarding
  are intentionally deferred.** Both involve project-level policy
  (when to move to emeritus, how to handle access removal, whether to
  send a farewell announcement) that needs per-project configuration
  before a skill can safely propose anything. These are candidate work
  items once the active-path skills stabilise and an adopter pilot
  surfaces the concrete policy knobs needed.
- **Mode boundary with Agentic Mentoring is intentionally fuzzy.** Two family
  skills (`mentoring-welcome`, `good-first-issue-author`) carry
  `mode: Mentoring` and are documented in [mentoring-mode.md](mentoring-mode.md);
  three carry `mode: Triage`. A later family-maturity review may
  formalise the boundary or merge the families; for now, both specs
  cross-reference each other.
- **`experimental` — no adopter pilot has run.** All five skills exist
  but no maintainer has run the full contributor-to-committer path
  end-to-end through the family. Shape may change as adopter pilots
  surface real-world usage patterns.
