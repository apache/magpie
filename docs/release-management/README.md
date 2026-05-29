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
the agent emits changes. The state-change boundaries (Drafting vs
Triage; agent never holds the signing key; agent never publishes)
stay identical too. See
[`process.md` § Adopter backends](process.md#adopter-backends)
for the full backend table and per-step mapping.

## Status

**Proposed.** No `release-*` skill code exists in the framework
today. This family lands as docs first (this README, the 14-step
[`process.md`](process.md), the per-skill [`spec.md`](spec.md), and
the adopter scaffold
[`projects/_template/release-management-config.md`](../../projects/_template/release-management-config.md))
so the lifecycle, the state-change boundaries, and the adopter
contract are reviewable independently from runtime behaviour.
The skills follow in subsequent PRs, each shipped flagged
`experimental` and tracked in [`docs/modes.md`](../modes.md). This
pattern matches [Mentoring](../mentoring/README.md).

Promotion of any skill in this family from `experimental` to
default-on, or from Drafting to a state-changing lane, requires
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

| Skill | Mode | Steps owned | Purpose |
|---|---|---|---|
| `release-prepare` | Drafting | 1, 2, 14 | Open the planning issue, draft the version-bump + changelog + NOTICE/LICENSE PR, then draft the post-release `-SNAPSHOT` bump. |
| `release-keys-sync` | Drafting | 3 | Draft the `KEYS` diff for a Release Manager cutting their first release for the project. Agent never holds the private key. |
| `release-rc-cut` | Drafting | 4, 5 | Emit the paste-ready command sequence, signed tag, build, detached signatures, checksums, `svn` import to `dist/dev/<project>/`. Agent never signs and never imports. |
| `release-verify-rc` | Triage / Pairing | 6 | Read-only pre-flight: signatures against the project's `KEYS`, checksums, license headers (Apache RAT), NOTICE/LICENSE presence, no prohibited binaries, version-string consistency. Voters can run it in their own dev loop before posting `+1`. |
| `release-vote-draft` | Drafting | 7 | Draft the `[VOTE]` email body to `dev@<project>`. Agent never sends. |
| `release-vote-tally` | Triage | 9 | Parse the vote thread, classify each reply (+1 / 0 / -1) binding vs non-binding against the PMC roster, propose `[RESULT] [VOTE]`. Conservative on ambiguous votes, refuses to count, flags `AMBIGUOUS, needs RM call`. |
| `release-promote` | Drafting | 10 | Emit the paste-ready `svn mv dist/dev → dist/release` command set plus commit message. Agent never moves; the human commit is the act of release. |
| `release-announce-draft` | Drafting | 11 | Draft the `[ANNOUNCE]` email body to `announce@apache.org` and the site-bump PR (download page, release notes, version banner). Agent never sends mail and never merges the site PR. |
| `release-archive-sweep` | Triage | 12 | Scan `dist/release/<project>/`, identify releases past retention, propose the `svn mv` sequence to `archive.apache.org`. Agent never moves. |
| `release-audit-report` | Triage (dashboard) | 13 | Read-only structured report per release, RM, voters with binding flags, artefacts with sigs and checksums, promotion revision, `[ANNOUNCE]` archive URL. Output appended to the project's audit log. |

Two non-negotiable boundaries cross every Drafting skill above:

- **The agent never holds, invokes, or proxies the Release
  Manager's private signing key.** Steps 3, 4, 10 emit paste-ready
  recipes; the RM runs every signing or `svn commit` operation as
  themselves. This mirrors
  [`security-cve-allocate`](../../.claude/skills/security-cve-allocate/SKILL.md)
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
spans the existing Triage and Drafting modes; no new mode is
introduced. See [`docs/modes.md`](../modes.md) for the
family-by-mode breakdown, `release-*` skills appear under the
**Triage** and **Drafting** subsections, each marked `proposed`.

The family's read-only dashboard skill
(`release-audit-report`)
sits in Triage because it classifies and reports against existing
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
