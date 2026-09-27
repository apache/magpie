<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — release trains, release managers, security team roster](#todo-project-name--release-trains-release-managers-security-team-roster)
  - [Release branches currently in flight](#release-branches-currently-in-flight)
  - [Current release managers](#current-release-managers)
  - [Known release-manager rotations](#known-release-manager-rotations)
  - [Release managers for releases currently relevant to the security tracker](#release-managers-for-releases-currently-relevant-to-the-security-tracker)
  - [Security team roster](#security-team-roster)
  - [What this means for sync and fix skills](#what-this-means-for-sync-and-fix-skills)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — release trains, release managers, security team roster

Fast-moving project state. Update every time a release ships, a new
release branch opens, or a security-team member joins / rotates off.

## Release branches currently in flight

TODO: list the project's active release branches. For each branch:

- the branch name (e.g. `v1-2-test`);
- which next release is expected to cut from it (e.g. `1.2.3`);
- whether new security fixes should default to this branch or a
  different one.

Example shape:

> - **`main`** — becomes the next minor release (X.Y+1.0 eventually).
> - **`v1-2-test`** — patch branch for the `1.2.x` series. Next patch is `1.2.3`.
> - **`v1-1-test`** — no further `1.1.x` releases planned.

## Current release managers

TODO: describe how to authoritatively identify the release manager
for a given cut. Two sources usually work:

1. TODO: the project's release-plan wiki / schedule page.
2. TODO: the `[RESULT][VOTE]` thread on the project's `<dev-list>`.
   The sender of the `[RESULT][VOTE] …` message **is** the release
   manager for that specific cut.

## Known release-manager rotations

TODO: list any active rotation rosters (providers / components / core
/ chart / …).

## Release managers for releases currently relevant to the security tracker

TODO: for each recently-shipped or upcoming release carrying security
fixes, record:

- the release name + date;
- the release manager (with email + GitHub handle);
- the source of that attribution (archive URL to the `[RESULT][VOTE]`
  thread);
- which CVEs shipped in it.

When this list becomes stale, the sync skill will surface it as a
blocker.

## Security team roster

TODO: the **authoritative** source is the collaborator list of the
tracker repository — anyone listed as a collaborator, regardless of
permission level, is on the security team.

```bash
gh api repos/<tracker>/collaborators --jq '.[].login'
```

Snapshot (update in the same change as member joins / rotates):

> TODO: list of GitHub handles.

## What this means for sync and fix skills

TODO: explicit defaults for the generic skills:

- Default milestone for a new patch-train security issue.
- Which backport labels the fix skill should apply by default.
- Legacy / do-not-use milestones (branches that have been retired).
- Any other sync-surfaced blockers specific to this project.
