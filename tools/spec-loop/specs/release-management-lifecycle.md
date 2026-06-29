<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Release-management lifecycle (end-to-end)
status: experimental
kind: feature
mode: Drafting
source: >
  MISSION.md § Initial Goals ("cut a first Apache release through the
  standard process within 3 months of resolution adoption"). README.md
  § Skill families (release-management, proposed). Designed spec-first in
  docs/release-management/ (README.md, process.md, spec.md) plus the
  adopter scaffold projects/_template/release-management-config.md.
  All ten skills have since shipped (release-prepare, release-keys-sync,
  release-rc-cut, release-vote-draft, release-archive-sweep,
  release-audit-report, release-announce-draft, release-verify-rc,
  release-vote-tally, release-promote).
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
- Skills (all ten shipped, all `experimental`): `release-prepare`
  (`mode: Drafting`) drafts the planning issue (Step 1), the prep PR with
  version bump / changelog / NOTICE / LICENSE (Step 2), and the
  post-release development-version bump PR (Step 14), never marking ready,
  merging, or closing; `release-keys-sync` (`mode: Drafting`) drafts the
  KEYS-file diff and paste-ready `svn` command sequence to add the RM's
  public key and validates key strength against the ASF floor, never
  holding or reading the private key (Step 3); `release-rc-cut`
  (`mode: Drafting`) emits the paste-ready tag / build / sign / checksum /
  staging command sequences for an RC, run locally by the RM with their
  own key (Steps 4–5); `release-announce-draft`
  (`mode: Drafting`) drafts
  the `[ANNOUNCE]` body and proposes the site-bump PR for a promoted
  release (Step 11), enforcing the one-hour promote-wait gate,
  `@apache.org` address reminder, Download Page link constraint, and
  no-send / no-auto-merge boundaries; `release-verify-rc` (`mode: Triage`)
  runs read-only RC pre-flight (signatures, checksums, RAT headers,
  NOTICE/LICENSE, prohibited binaries, version consistency, Step 6);
  `release-vote-draft` (`mode: Drafting`) drafts the `[VOTE]` email body
  and planning-issue comment after a PASS pre-flight, never sending or
  posting (Step 7); `release-vote-tally` (`mode: Triage`) classifies
  +1/0/-1 binding vs non-binding once the window closes and drafts the
  `[RESULT]` (Step 9); `release-promote` (`mode: Drafting`) emits the
  backend-shaped staging→release promotion command set for a vote-passed
  release (Step 10); `release-archive-sweep` (`mode: Triage`) scans the
  dist area and proposes the command set to move past-retention releases
  to the archive, read-only on the dist surface (Step 12); and
  `release-audit-report` (`mode: Triage`) assembles the per-release audit
  record from the planning issue, vote thread, artefact list, and announce
  archive URL and proposes the audit-log PR, read-only on every release
  surface (Step 13). All ten skills have now shipped.
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
  release-* skill from `experimental` to default-on, or from Agentic Drafting to a
  state-changing lane, requires evidence from Release Managers and binding
  voters that the process is healthier (fewer stalled RCs, shorter
  time-to-`[ANNOUNCE]`, fewer reverted promotions).
- **Audit records are structured.** `release-audit-report` output should
  follow a schema/template with required fields for release version, RC
  artefacts, vote thread, tally outcome, promotion revision, announcement
  URL, archive state, and follow-up notes. Missing required fields are a
  report finding, not silently omitted prose.

## Out of scope

- Holding, invoking, or proxying the RM's private signing key.
- Publishing the release: the `svn mv` promotion, the `[ANNOUNCE]` send,
  and the site-bump merge are human acts.
- A new mode. Release-management is a family spanning the existing Agentic Triage
  and Agentic Drafting modes; it introduces no new mode.

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
4. `release-audit-report` validates the audit record against the
   required-field schema and flags incomplete lifecycle evidence before
   proposing an audit-log PR.

## Validation

```bash
test -f docs/release-management/spec.md
test -f docs/release-management/process.md
test -f projects/_template/release-management-config.md
test -f .claude/skills/magpie-release-prepare/SKILL.md
test -f .claude/skills/magpie-release-keys-sync/SKILL.md
test -f .claude/skills/magpie-release-rc-cut/SKILL.md
test -f .claude/skills/magpie-release-vote-draft/SKILL.md
test -f .claude/skills/magpie-release-archive-sweep/SKILL.md
test -f .claude/skills/magpie-release-audit-report/SKILL.md
test -f .claude/skills/magpie-release-announce-draft/SKILL.md
test -f .claude/skills/magpie-release-verify-rc/SKILL.md
test -f .claude/skills/magpie-release-vote-tally/SKILL.md
test -f .claude/skills/magpie-release-promote/SKILL.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-announce-draft/
```

## Known gaps

- **All ten skills have shipped** — `release-prepare`, `release-keys-sync`,
  `release-rc-cut`, `release-vote-draft`, `release-archive-sweep`,
  `release-audit-report`, `release-announce-draft`, `release-verify-rc`,
  `release-vote-tally`, `release-promote` — each `experimental` with an
  eval suite. The family is feature-complete; no skill remains `proposed`.
- **Health-evidence promotion criteria are unmeasured.** No adopter has
  cut a full release through the family yet, so the RM/binding-voter
  evidence window that would justify default-on or a state-changing lane
  has no data behind it.
- **Release audit record schema is prose-only.** The audit-report skill
  exists, but there is no structured schema/template that downstream
  review can validate. The plan tracks a schema and eval fixtures for
  incomplete records.
