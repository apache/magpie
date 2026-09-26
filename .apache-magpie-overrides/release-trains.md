<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — release trains, release managers, security team roster](#apache-magpie--release-trains-release-managers-security-team-roster)
  - [Release branches currently in flight](#release-branches-currently-in-flight)
  - [Current release managers](#current-release-managers)
  - [Known release-manager rotations](#known-release-manager-rotations)
  - [Release managers for releases currently relevant to the security tracker](#release-managers-for-releases-currently-relevant-to-the-security-tracker)
  - [Security team roster](#security-team-roster)
  - [What this means for sync and fix skills](#what-this-means-for-sync-and-fix-skills)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — release trains, release managers, security team roster

Fast-moving project state. Update every time a release ships, a new
release branch opens, or a security-team member joins / rotates off.

## Release branches currently in flight

- **`main`** — the only release train. Releases are tagged from `main`
  (`<version>-rcN`, then `<version>`); there are no maintenance branches.
  Latest release: `0.1.0` (2026-07-12).

Template guidance — for each branch list:

- the branch name (e.g. `v1-2-test`);
- which next release is expected to cut from it (e.g. `1.2.3`);
- whether new security fixes should default to this branch or a
  different one.

Example shape:

> - **`main`** — becomes the next minor release (X.Y+1.0 eventually).
> - **`v1-2-test`** — patch branch for the `1.2.x` series. Next patch is `1.2.3`.
> - **`v1-1-test`** — no further `1.1.x` releases planned.

## Current release managers

The sender of the `[RESULT][VOTE]` message on `dev@magpie.apache.org`
is the release manager for that cut. Sources:

1. The `release-planning` GitHub issue for the release on `apache/magpie`.
2. The `[RESULT][VOTE]` thread on `dev@magpie.apache.org`.
   The sender of the `[RESULT][VOTE] …` message **is** the release
   manager for that specific cut.

## Known release-manager rotations

None — a single release train with a per-release RM.

- `0.1.0` (2026-07-12) — RM: Jarek Potiuk (`potiuk@apache.org`, GitHub `@potiuk`).

## Release managers for releases currently relevant to the security tracker

None — no Apache Magpie release has carried a security fix yet.

Template guidance — for each such release record:

- the release name + date;
- the release manager (with email + GitHub handle);
- the source of that attribution (archive URL to the `[RESULT][VOTE]`
  thread);
- which CVEs shipped in it.

When this list becomes stale, the sync skill will surface it as a
blocker.

## Security team roster

Not applicable — Apache Magpie has no private security tracker; security
reports follow the ASF default process via `security@apache.org`, handled
by the Magpie PMC (see `pmc-roster.md`).

Template guidance: the **authoritative** source is the collaborator list of the
tracker repository — anyone listed as a collaborator, regardless of
permission level, is on the security team.

```bash
gh api repos/<tracker>/collaborators --jq '.[].login'
```

Snapshot (update in the same change as member joins / rotates):

> None — no tracker repository.

## What this means for sync and fix skills

Defaults for the generic skills — no release milestones, no backport labels
(releases cut from `main` only), no retired milestones, no project-specific
sync blockers. Template checklist:

- Default milestone for a new patch-train security issue.
- Which backport labels the fix skill should apply by default.
- Legacy / do-not-use milestones (branches that have been retired).
- Any other sync-surfaced blockers specific to this project.
