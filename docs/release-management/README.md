<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Release-management skill family](#release-management-skill-family)
  - [Status](#status)
  - [Skills](#skills)
  - [Deep documentation](#deep-documentation)
  - [Adopter contract](#adopter-contract)
  - [Mode mapping](#mode-mapping)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Release-management skill family

> **Scope — `organization: ASF` · 🪶 ASF-specific.** This family encodes Apache Software
> Foundation processes (the 14-step release lifecycle) and assumes an ASF adopter
> profile by default. Non-ASF projects can still adopt it through the
> adapter/config layer, but it carries ASF assumptions the generic families do not.

End-to-end automation for an ASF project's release lifecycle,
from the planning issue and version bump through to `[ANNOUNCE]`
on `announce@apache.org`, archive sweep, and the per-release
audit log. Ten skills that compose into the canonical 14-step
process documented in [`process.md`](process.md).

Why a framework skill family? Every ASF project runs essentially
the same release process: version bump, `KEYS` reconciliation, RC
signed with the Release Manager's key, staged to
`dist/apache.org/repos/dist/dev/<project>/`, voted on `dev@` per
[`release-policy.html § release approval`](https://www.apache.org/legal/release-policy.html#release-approval),
promoted to `dist/release/<project>/`, announced on
`announce@apache.org` per
[`release-policy.html § announcements`](https://www.apache.org/legal/release-policy.html#release-announcements),
and archived past retention per
[`release-distribution`](https://infra.apache.org/release-distribution.html).
The procedural shape is foundation-wide; the project-specific
content (release-train identity, build invocation, `KEYS` file
path, vote-window length, retention rule, audit-log location)
plugs in through [`<project-config>/`](../../projects/_template/)
just like the security family.

Non-ASF adopters are first-class adopters of this family, not a
follow-up case. The 14-step lifecycle is described in ASF
terminology because the framework's first pilot is an ASF PMC,
but every step that touches an ASF-specific surface is implemented
as a backend call the adopter selects in
[`release-management-config.md`](../../projects/_template/release-management-config.md).
Three dimensions parametrise the lifecycle, with no ASF assumption
baked into the install path:

- **Distribution backend** (`release_dist_backend`): `svnpubsub`
  (ASF), `github-releases`, `s3`, `self-hosted`.
- **Approval mechanism** (`release_approval_mechanism`):
  `dev-list-vote` (ASF), `github-discussion`, `pr-approval`,
  `maintainer-roster`.
- **Announcement backend** (`release_announce_backend`):
  `announce-list` (ASF), `github-release-notes`, `site-post`,
  `discord-channel`.

The 14 steps stay identical across backends; only the command set
the agent emits changes. The state-change boundaries (Agentic Drafting vs
Agentic Triage; agent never holds the signing key; agent never publishes)
stay identical too. See
[`process.md` § Adopter backends](process.md#adopter-backends)
for the full backend table and per-step mapping.

## Status

**Experimental — all 10 skills shipped.** The family is
feature-complete; every skill landed as `experimental` with an
eval suite:

| Skill | PR | Step(s) |
|---|---|---|
| [`release-prepare`](../../skills/release-prepare/SKILL.md) | #540 | 1, 2, 14 |
| [`release-keys-sync`](../../skills/release-keys-sync/SKILL.md) | #541 | 3 |
| [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) | #543 | 4, 5 |
| [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) | #537 | 6 |
| [`release-vote-draft`](../../skills/release-vote-draft/SKILL.md) | #582 | 7 |
| [`release-vote-tally`](../../skills/release-vote-tally/SKILL.md) | #533 | 9 |
| [`release-promote`](../../skills/release-promote/SKILL.md) | #544 | 10 |
| [`release-announce-draft`](../../skills/release-announce-draft/SKILL.md) | #512 | 11 |
| [`release-archive-sweep`](../../skills/release-archive-sweep/SKILL.md) | #551 | 12 |
| [`release-audit-report`](../../skills/release-audit-report/SKILL.md) | #552 | 13 |

Every skill is flagged `experimental` and tracked in
[`docs/modes.md`](../modes.md).

The family landed as docs first (this README, the 14-step
[`process.md`](process.md), the per-skill [`spec.md`](spec.md), and
the adopter scaffold
[`projects/_template/release-management-config.md`](../../projects/_template/release-management-config.md))
so the lifecycle, the state-change boundaries, and the adopter
contract are reviewable independently from runtime behaviour.
This pattern matches [Mentoring](../mentoring/README.md).

Promotion of any skill in this family from `experimental` to
default-on, or from Agentic Drafting to a state-changing lane, requires
evidence sourced from Release Managers and binding voters that
the project's release process is healthier (fewer stalled
RCs, shorter time-to-`[ANNOUNCE]`, fewer reverted promotions),
not throughput numbers alone. The evidence window is set by
adopter governance, not by this family.

See [`MISSION.md` § Initial Goals](../../MISSION.md#initial-goals)
for the commitment to *cut a first Apache release through the
standard process within 3 months of resolution adoption*; this
family operationalises it.

## Skills

The skill table below names each `release-*` skill, its mode, and
the lifecycle step(s) it owns. Read [`spec.md`](spec.md) for the
per-skill state-change boundary; read [`process.md`](process.md)
for the step it executes against.

| Skill | Mode | Steps owned | Status | Purpose |
|---|---|---|---|---|
| [`release-prepare`](../../skills/release-prepare/SKILL.md) | Agentic Drafting | 1, 2, 14 | **experimental** | Open the planning issue, draft the version-bump + changelog + NOTICE/LICENSE PR, then draft the post-release `-SNAPSHOT` bump. |
| [`release-keys-sync`](../../skills/release-keys-sync/SKILL.md) | Agentic Drafting | 3 | **experimental** | Draft the `KEYS` diff for a Release Manager cutting their first release for the project. Agent never holds the private key. |
| [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) | Agentic Drafting | 4, 5 | **experimental** | Emit the paste-ready command sequence, signed tag, build, detached signatures, checksums, `svn` import to `dist/dev/<project>/`. Agent never signs and never imports. |
| [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) | Agentic Triage / Agentic Pairing | 6 | **experimental** | Read-only pre-flight: signatures against the project's `KEYS`, checksums, license headers (Apache RAT), NOTICE/LICENSE presence, no prohibited binaries, version-string consistency. Voters can run it in their own dev loop before posting `+1`. |
| [`release-vote-draft`](../../skills/release-vote-draft/SKILL.md) | Agentic Drafting | 7 | **experimental** | Draft the `[VOTE]` email body to `dev@<project>`. Agent never sends. |
| [`release-vote-tally`](../../skills/release-vote-tally/SKILL.md) | Agentic Triage | 9 | **experimental** | Parse the vote thread, classify each reply (+1 / 0 / -1) binding vs non-binding against the PMC roster, propose `[RESULT] [VOTE]`. Conservative on ambiguous votes, refuses to count, flags `AMBIGUOUS, needs RM call`. |
| [`release-promote`](../../skills/release-promote/SKILL.md) | Agentic Drafting | 10 | **experimental** | Emit the paste-ready `svn mv dist/dev → dist/release` command set plus commit message. Agent never moves; the human commit is the act of release. |
| [`release-announce-draft`](../../skills/release-announce-draft/SKILL.md) | Agentic Drafting | 11 | **experimental** | Draft the `[ANNOUNCE]` email body to `announce@apache.org` and the site-bump PR (download page, release notes, version banner). Agent never sends mail and never merges the site PR. |
| [`release-archive-sweep`](../../skills/release-archive-sweep/SKILL.md) | Agentic Triage | 12 | **experimental** | Scan `dist/release/<project>/`, identify releases past retention, propose the `svn mv` sequence to `archive.apache.org`. Agent never moves. |
| [`release-audit-report`](../../skills/release-audit-report/SKILL.md) | Agentic Triage (dashboard) | 13 | **experimental** | Read-only structured report per release, RM, voters with binding flags, artefacts with sigs and checksums, promotion revision, `[ANNOUNCE]` archive URL. Output appended to the project's audit log. |

Two non-negotiable boundaries cross every Agentic Drafting skill above:

- **The agent never holds, invokes, or proxies the Release
  Manager's private signing key.** Steps 3, 4, 10 emit paste-ready
  recipes; the RM runs every signing or `svn commit` operation as
  themselves. This mirrors
  [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md)
  (Vulnogram URL + paste-ready JSON, human submits) and satisfies
  [RFC-AI-0004 Principle 1](../rfcs/RFC-AI-0004.md#principle-1--human-in-the-loop-on-every-state-change).
- **The agent never publishes the release.** Steps 10
  (`svn mv dist/dev → dist/release`) and 11 (`[ANNOUNCE]` send,
  site bump merge) are the moments of release; the agent drafts
  artefacts, the RM and the PMC execute and merge.

## Deep documentation

- [**`process.md`**](process.md), the 14-step lifecycle with
  Mermaid flowchart + per-step description; the label-lifecycle
  state diagram + label reference table. The authoritative
  process reference.
- [**`spec.md`**](spec.md), per-skill scope, state-change
  boundary, hand-off protocol, adopter knobs. The contract the
  future skill implementations must satisfy.
- [**`svn-release-runbook.md`**](svn-release-runbook.md), the
  hands-on copy-paste command sequence for the `svnpubsub` backend:
  package a tagged revision as a signed source `.zip` with SHA-512
  and stage it to `dist/dev/` (lifecycle Steps 4–5). The longhand
  companion to [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md).
- [**`atr-release-runbook.md`**](atr-release-runbook.md), the
  counterpart runbook for the `atr` (**Apache Trusted Releases**)
  backend: compose a signed candidate in ATR, let the platform run
  the policy checks and drive the `[VOTE]`, then *finish* to publish
  and announce. Same 14-step lifecycle and same skills as the
  `svnpubsub` runbook; ATR replaces the mechanics of Steps 5–11. ATR
  is in alpha — the forward-looking backend, tracked against the
  [MISSION § first-release commitment](../../MISSION.md#initial-goals).

Two documents that **do not** ship in this family but are
referenced from it:

- [`<project-config>/release-trains.md`](../../projects/_template/release-trains.md)
 , release-train identity (already present in the adopter
  scaffold for security use; release-management reuses it).
- [`<project-config>/release-management-config.md`](../../projects/_template/release-management-config.md)
 , the family's adopter contract (new in this PR).

## Adopter contract

The skills resolve project-specific content from the release-
workflow files in
[`<project-config>/`](../../projects/_template/), see the
adopter scaffold's
[`README.md`](../../projects/_template/README.md) for the
file-by-file index. Required at minimum:

- `project.md`, identity, repos, mailing lists, tools
- `release-management-config.md`, vote window, vote-pass rule,
  signing-key requirements, audit-log location, retention rule,
  build command, KEYS file path
- `release-trains.md`, release-train identity (shared with the
  security family)
- `release-build.md`, build invocation, digest set, binary-exclude
  list (new in this PR; minimal scaffold)
- `pmc-roster.md`, PMC member roster used by
  `release-vote-tally`
  to classify binding vs non-binding votes (new in this PR;
  minimal scaffold)
- `site-repo.md`, site-bump PR target for
  `release-announce-draft`
  (new in this PR; minimal scaffold)

## Mode mapping

Release-management is a **family**, not a mode. The lifecycle
spans the existing Agentic Triage and Agentic Drafting modes; no new mode is
introduced. See [`docs/modes.md`](../modes.md) for the
family-by-mode breakdown; `release-*` skills appear under the
**Agentic Triage** and **Agentic Drafting** subsections (all ten skills are now
`experimental`; the family is feature-complete).

The family's read-only dashboard skill
(`release-audit-report`)
sits in Agentic Triage because it classifies and reports against existing
state, not because it routes inbound work. The
[`docs/modes.md` § Outside the modes](../modes.md#outside-the-modes)
section is reserved for framework infrastructure (`setup-*`,
`issue-reassess-stats`, isolation tooling) and the audit skill
does not belong there, it is project-facing maintainership work.

## Cross-references

- [`process.md`](process.md), [`spec.md`](spec.md), within this
  family.
- [`MISSION.md` § Initial Goals](../../MISSION.md#initial-goals),
  the standard-release commitment this family operationalises.
- [`docs/modes.md`](../modes.md), the mode taxonomy each skill
  in this family inhabits.
- [`docs/security/README.md`](../security/README.md), the
  precedent for a multi-skill ASF-process family with shared
  state-change-boundary discipline.
- [`docs/mentoring/README.md`](../mentoring/README.md), the
  precedent for spec-before-code on a proposed family.
- [ASF release policy](https://www.apache.org/legal/release-policy.html), [ASF release distribution](https://infra.apache.org/release-distribution.html), [ASF release signing](https://infra.apache.org/release-signing.html), [ASF licensing-howto](https://www.apache.org/legal/resolved.html), [Apache RAT](https://creadur.apache.org/rat/), the canonical foundation references the lifecycle is anchored to.
