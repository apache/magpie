<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Release-management lifecycle (end-to-end)
status: proposed
kind: feature
mode: Drafting
source: >
  MISSION.md § Initial Goals ("cut a first Apache release through the
  standard process within 3 months of resolution adoption"). README.md
  § Skill families (release-management, proposed). Designed spec-first in
  docs/release-management/ (README.md, process.md, spec.md) plus the
  adopter scaffold projects/_template/release-management-config.md. No
  release-* skill code exists yet.
acceptance:
  - The family's design (14-step process, per-skill state-change
    boundaries, adopter contract) is reviewable independently of any
    runtime skill; it already is, in docs/release-management/.
  - Each release-* skill, when it lands, ships flagged `experimental` and
    carries `mode: Drafting` or `mode: Triage` per the skill table.
  - The agent never holds, invokes, or proxies the Release Manager's
    signing key, and never publishes the release; steps 3, 4, 10, 11 emit
    paste-ready recipes the human executes as themselves.
---

# Release-management lifecycle

## What it does

End-to-end automation for an ASF project's release lifecycle, from the
planning issue and version bump through to `[ANNOUNCE]` on
`announce@apache.org`, the archive sweep, and the per-release audit log.
Ten skills compose into the canonical 14-step process. The procedural
shape is foundation-wide; project-specific content (release-train
identity, build invocation, `KEYS` path, vote-window length, retention
rule, audit-log location) plugs in through `<project-config>/`, exactly
as the security family does. Non-ASF adopters are first-class: the
distribution backend, approval mechanism, and announcement backend each
parametrise the lifecycle without baking in an ASF assumption.

This is the load-bearing parallel to the security-issue lifecycle: a
multi-skill, high-procedure ASF-process family with shared
state-change-boundary discipline, designed docs-first before any skill
code lands.

## Where it lives

- Design docs (present today): `docs/release-management/README.md`
  (family overview + skill table), `docs/release-management/process.md`
  (14-step lifecycle, Mermaid flow, label reference),
  `docs/release-management/spec.md` (per-skill scope and state-change
  boundary).
- Adopter contract: `projects/_template/release-management-config.md`,
  `projects/_template/release-build.md`, `projects/_template/pmc-roster.md`,
  `projects/_template/site-repo.md`, and the shared
  `projects/_template/release-trains.md`.
- Skills (all `proposed`, none implemented yet): `release-prepare`,
  `release-keys-sync`, `release-rc-cut`, `release-verify-rc`,
  `release-vote-draft`, `release-vote-tally`, `release-promote`,
  `release-announce-draft`, `release-archive-sweep`,
  `release-audit-report`.
- Adapters it will read/draft through: `tools/github`, `tools/ponymail`
  (vote threads), `tools/gmail` (announce/vote drafts), plus the project's
  `svn` dist tree as a distribution backend.

## Behaviour & contract

- **The agent never holds the signing key.** Steps 3 (`KEYS`), 4 (RC tag,
  sign, checksums, `svn` import to `dist/dev/<project>/`), and 10
  (`svn mv dist/dev → dist/release`) emit paste-ready command recipes; the
  Release Manager runs every signing and `svn commit` operation as
  themselves. Mirrors `security-cve-allocate` (Vulnogram URL + paste-ready
  JSON, human submits).
- **The agent never publishes the release.** Step 10 (promotion) and step
  11 (`[ANNOUNCE]` send + site-bump merge) are the moments of release; the
  agent drafts artefacts, the RM and PMC execute and merge.
- **Drafts, never sends.** `[VOTE]` (step 7) and `[ANNOUNCE]` (step 11)
  email bodies are drafted to the maintainer's outbox; no skill calls a
  send.
- **Conservative tally.** `release-vote-tally` classifies +1/0/-1 binding
  vs non-binding against the PMC roster and refuses to count ambiguous
  votes, flagging `AMBIGUOUS, needs RM call` rather than guessing.
- **Read-only verification.** `release-verify-rc` (signatures, checksums,
  RAT license headers, NOTICE/LICENSE, prohibited binaries, version
  consistency) and `release-audit-report` make no state change; voters can
  run verification in their own dev loop before posting `+1`.
- **Promotion gated on health evidence, not throughput.** Moving any
  release-* skill from `experimental` to default-on, or from Drafting to a
  state-changing lane, requires evidence from Release Managers and binding
  voters that the process is healthier (fewer stalled RCs, shorter
  time-to-`[ANNOUNCE]`, fewer reverted promotions).

## Out of scope

- Holding, invoking, or proxying the RM's private signing key.
- Publishing the release: the `svn mv` promotion, the `[ANNOUNCE]` send,
  and the site-bump merge are human acts.
- A new mode. Release-management is a family spanning the existing Triage
  and Drafting modes; it introduces no new mode.

## Acceptance criteria

1. The 14-step process, per-skill state-change boundaries, and adopter
   contract are reviewable from `docs/release-management/` without any
   skill code (they are today).
2. Each `release-*` skill, as it lands, validates under
   `skill-and-tool-validate`, ships `experimental`, and carries the
   `mode` its skill-table row assigns.
3. No skill in the family signs, imports, promotes, sends, or merges on
   autopilot; the key-holding and publishing steps emit paste-ready
   recipes only.

## Validation

```bash
test -f docs/release-management/spec.md
test -f docs/release-management/process.md
test -f projects/_template/release-management-config.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **No `release-*` skill code exists yet.** The family is `proposed`,
  designed docs-first (mirroring Mentoring). All ten skills land in
  follow-up PRs, each flagged `experimental`. The plan pass turns each
  un-implemented skill in the `docs/release-management/` table into a work
  item.
- **No eval suites exist** under `tools/skill-evals/evals/release-*/`;
  each skill needs one per the per-skill-eval convention before it can
  graduate from `experimental`.
- **Health-evidence promotion criteria are unmeasured.** No adopter has
  cut a release through the family yet, so the RM/binding-voter evidence
  window that would justify default-on or a state-changing lane has no
  data behind it.
