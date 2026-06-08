<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Pairing mode
status: experimental
kind: feature
mode: Pairing
source: >
  MISSION.md § Technical scope (Pairing) and § Initial Goals ("Ship at
  least one Pairing skill family in v1"). docs/modes.md § Pairing
  (experimental, 2 skills).
acceptance:
  - At least one Pairing skill exists and validates (v1 goal).
  - Pairing skills run in the developer's OWN dev loop and make no state
    change on behalf of the project (read-only / hand-back).
  - Mentorship is intrinsic: the agent handles implementation-detail
    review so the human conversation stays on design and reasoning.
---

# Pairing mode

## What it does

The developer-side counterpart to the project-side modes. Pairing skills
run in a maintainer's or contributor's *own* dev loop: multi-agent review
pipelines, self-review and pre-flight patterns, and scoped fix drafting
under the developer's driver's seat. Mentorship is intrinsic — the agent
absorbs mechanical implementation-detail review so the human-to-human
conversation stays on design and the trade-offs the project cares about,
protecting the ASF contribution path (contributor → committer → PMC).

## Where it lives

- Skill: `pairing-self-review` — structured pre-flight self-review of
  local changes before opening a PR. Read-only; returns a structured
  report with no external writes. Ships `mode: Pairing` + `experimental`.
- Skill: `pairing-multi-agent-review` — fans the diff through three
  independent, axis-focused sub-agents (correctness, security,
  conventions); merges findings with deduplication and severity ranking
  into a report in the same format as `pairing-self-review`. Each pass
  is isolated so findings from one axis cannot suppress or bias the
  others. Read-only; no state change. Ships `mode: Pairing` + `experimental`.

## Behaviour & contract

- **No state change on the project's behalf.** Pairing skills are the
  developer's toolkit; they end at a report or a local branch.
- Same skill format and sandbox/privacy posture as the project-side modes.
- **Ships before Auto-merge** in the roadmap (MISSION sequencing): Pairing
  must establish that human reasoning, not implementation chatter, is the
  load-bearing part of the workflow before any auto-merge is considered.

## Out of scope

- Acting on issues/PRs/threads on the project's behalf (that is
  Triage/Mentoring/Drafting).
- Auto-merge — deliberately off by MISSION sequencing; not built.

## Acceptance criteria

1. ≥1 Pairing skill exists, validates, and is read-only/hand-back.
2. `docs/modes.md` Pairing row reflects the shipped count and status.
3. `pairing-multi-agent-review` fans through three independent passes
   and merges findings without cross-pass anchoring.

## Validation

```bash
ls .claude/skills/ | grep -q '^magpie-pairing-' && echo "pairing skills present" || echo "GAP: no pairing skills"
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **`experimental` — no adopter pilot has run.** Both `pairing-self-review`
  and `pairing-multi-agent-review` shipped; no contributor-sentiment
  evaluation has run yet; shape may change.
