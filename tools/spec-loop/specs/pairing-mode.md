<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Agentic Pairing mode
status: experimental
kind: feature
mode: Pairing
source: >
  MISSION.md § Technical scope (Pairing) and § Initial Goals ("Ship at
  least one Pairing skill family in v1"). docs/modes.md § Pairing
  (experimental, 3 skills). Implemented in plugins/magpie-pairing/skills/
  (self-review, multi-agent-review) and
  plugins/magpie-pr-management/skills/pre-first-pr-check/.
acceptance:
  - At least one Agentic Pairing skill exists and validates (v1 goal).
  - Agentic Pairing skills run in the developer's OWN dev loop and make no state
    change on behalf of the project (read-only / hand-back).
  - Mentorship is intrinsic: the agent handles implementation-detail
    review so the human conversation stays on design and reasoning.
---

# Agentic Pairing mode

## What it does

The developer-side counterpart to the project-side modes. Agentic Pairing skills
run in a maintainer's or contributor's *own* dev loop: multi-agent review
pipelines, self-review and pre-flight patterns, and scoped fix drafting
under the developer's driver's seat. Mentorship is intrinsic — the agent
absorbs mechanical implementation-detail review so the human-to-human
conversation stays on design and the trade-offs the project cares about,
protecting the ASF contribution path (contributor → committer → PMC).

## Where it lives

- Skill: `pairing-self-review` (`plugins/magpie-pairing/skills/self-review/`)
  — structured pre-flight self-review of
  local changes before opening a PR. Read-only; returns a structured
  report with no external writes. Ships `mode: Pairing` + `experimental`.
- Skill: `pairing-multi-agent-review`
  (`plugins/magpie-pairing/skills/multi-agent-review/`) — fans the diff through three
  independent, axis-focused sub-agents (correctness, security,
  conventions); merges findings with deduplication and severity ranking
  into a report in the same format as `pairing-self-review`. Each pass
  is isolated so findings from one axis cannot suppress or bias the
  others. Read-only on the project; its only writes are the optional local
  staging file below. Ships `mode: Pairing` + `experimental`.
- Claude Code mod: `plugins/magpie-pairing/hooks/multi-agent-review-pane.ts`
  (types in `types.ts` / `types.d.ts`, tests in
  `multi-agent-review-pane.test.ts`), wired by `hooks/hooks.json`
  (#2274, #2323). Codex reads the plugin's `.codex-plugin/plugin.json`
  and an empty `hooks/codex-hooks.json` instead.
- Skill: `pre-first-pr-check`
  (`plugins/magpie-pr-management/skills/pre-first-pr-check/`, linked from
  `skills/pre-first-pr-check`) — newcomer-focused checklist on a local
  branch before the first PR: CONTRIBUTING conventions, SPDX headers on new
  files, commit-message shape including the `Generated-by:` trailer, and the
  placeholder convention.
  Read-only; no PR and no external writes.
  Ships `mode: Pairing` + `experimental`, but is packaged in the
  `magpie-pr-management` plugin (`family: pr-management`), not in
  `magpie-pairing`.
- Related, not a Pairing skill: the `magpie-adversarial-review` plugin's
  per-harness command (`/magpie-adversarial-review:adversarial-review` in
  Claude Code) lets a developer ask other models for a read-only second
  read of a branch, diff or PR in their own loop
  ([adversarial review](adversarial-review.md)).

## Behaviour & contract

- **No state change on the project's behalf.** Agentic Pairing skills are the
  developer's toolkit; they end at a report or a local branch.
- Same skill format and sandbox/privacy posture as the project-side modes.
- **A prompt-injection attempt in a diff is recorded, not obeyed.** Each
  `pairing-multi-agent-review` pass lists it in `injection_attempts` and
  emits no in-axis finding for it; Step 3 aggregates the lists into the
  Security axis (#2323).
- **Curation round trip.** Step 3 may stage the merged findings as
  `.magpie-pairing-review-<head_sha>.json` and run `test -f` on it, which
  is what notifies the mod. Step 4 applies
  `.magpie-pairing-decision-<head_sha>.json` only when its schema version
  and head SHA match, it is not invalidated, and its source digest matches
  the staged payload; dismissed findings then leave the blocking and
  advisory counts and are annotated as dismissed. A mutating `git` command
  invalidates the decision file.
- **Evidence-gated dependency-version findings.** `pairing-self-review` inventories every mandatory direct and transitive constraint path, applies environment markers, and classifies the effective intersection as broken, compatible, or unknown before surfacing a compatibility finding.
  An empty intersection is always `broken (uninstallable)`, never unknown.
  Every such finding carries the complete constraint ledger.
  Remediation follows policy read from the resolved explicit base commit, the default merge base, or `HEAD` for staged-only review;
  it never follows policy introduced by the changes under review or copies conventions from another project.
- **Ships before Agentic Autonomous** in the roadmap (MISSION sequencing): Agentic Pairing
  must establish that human reasoning, not implementation chatter, is the
  load-bearing part of the workflow before any auto-merge is considered.
- **The multi-agent review comparison pane is additive.** Under Claude Code, the mod (`plugins/magpie-pairing/hooks/`) provides the side-by-side comparison pane UI (`[Accept]`, `[Dismiss]`, `[Reset]` across `Correctness`, `Security`, `Conventions`), session state atom, payload sanitization, path confinement, runtime `$.fs` IPC (`.magpie-pairing-review-<sha>.json` / `.magpie-pairing-decision-<sha>.json`), `$.ui.open({ component: 'Pane' })`, `ui.press` button routing, and `multi-agent-review` skill integration. On other harnesses or when the mod is absent, the skill continues with its standard markdown report.

## Out of scope

- Acting on issues/PRs/threads on the project's behalf (that is
  Agentic Triage/Agentic Mentoring/Agentic Drafting).
- Agentic Autonomous — deliberately off by MISSION sequencing; not built.

## Acceptance criteria

1. ≥1 Agentic Pairing skill exists, validates, and is read-only/hand-back.
2. `docs/modes.md` Agentic Pairing row reflects the shipped count and status.
3. `pairing-multi-agent-review` fans through three independent passes
   and merges findings without cross-pass anchoring.
4. `pairing-self-review` never surfaces a dependency-version compatibility finding without a complete constraint ledger and a supported `broken`, `compatible`, or `unknown` classification.
   Remediation follows adopter policy read from the resolved explicit base commit, the default merge base, or staged-only `HEAD`.

## Validation

```bash
ls .claude/skills/ | grep -q '^magpie-pairing-' && echo "pairing skills present" || echo "GAP: no pairing skills"
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
prek run check-claude-mods --hook-stage manual --all-files
```

## Known gaps

- **`experimental` — no adopter pilot has run.** `pairing-self-review`,
  `pairing-multi-agent-review` and `pre-first-pr-check` shipped; no
  contributor-sentiment evaluation has run yet; shape may change.
- **The Pairing skills are split across two plugins.** An adopter who
  installs only `magpie-pairing` does not get `pre-first-pr-check`, and the
  validation command above, which greps for the `magpie-pairing-` prefix,
  does not see it either.
