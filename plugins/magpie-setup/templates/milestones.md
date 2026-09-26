<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — milestone conventions](#todo-project-name--milestone-conventions)
  - [Creating a missing milestone](#creating-a-missing-milestone)
  - [Defaults and policy](#defaults-and-policy)
  - [What the milestone unlocks](#what-the-milestone-unlocks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — milestone conventions

The project uses GitHub milestones on its `<tracker>` repository to
pin an issue to the release it ships in. Milestones are the hand-off
signal from the remediation developer to the release manager; the
`security-issue-sync` skill creates and assigns them as part of the
`pr merged` → `fix released` transition.

TODO: list every milestone format the project uses, one row per
release train.

| Milestone format | Applies to scope label | Example | Source of the version |
|---|---|---|---|
| TODO: e.g. `Foo-X.Y.Z` | TODO: scope label that triggers this milestone format | TODO: e.g. `Foo-2.6.2` | TODO: release-plan page / `[RESULT][VOTE]` thread |

## Creating a missing milestone

TODO: the `gh api` recipe the sync skill uses when the needed
milestone does not yet exist in `<tracker>`. Most projects keep
this as:

```bash
gh api -X POST repos/<tracker>/milestones \
  -f title="TODO: milestone title" \
  -f description="TODO: optional short description"
```

## Defaults and policy

TODO:

- Default milestone for a new patch-train security issue.
- Legacy milestones that exist in the tracker but should not receive
  new security fixes.
- Policy for bumping a fix to the next **minor** release instead of
  the next patch (high-risk changes, bundles with other changes).

## What the milestone unlocks

Once the milestone is set on a `pr merged` tracker, the
`security-issue-sync` skill watches for the release to ship and
proposes the `pr merged` → `fix released` label swap, which hands
ownership off to the release manager for steps 13–15. See the
repo-level [`../../README.md`](../../../README.md) for the step-by-step
lifecycle.
