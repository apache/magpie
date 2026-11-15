<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — release-prepare overrides](#apache-magpie--release-prepare-overrides)
  - [Override 1 — Run the pre-release sweep before the planning issue](#override-1--run-the-pre-release-sweep-before-the-planning-issue)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — release-prepare overrides

Agent-readable overrides `release-prepare` applies when the Apache Magpie release manager prepares a Magpie release.
Contract: [`docs/setup/agentic-overrides.md`](../docs/setup/agentic-overrides.md).

## Override 1 — Run the pre-release sweep before the planning issue

Before Step 1 (`plan`) drafts the planning issue, run [`pre-release-sweep`](../skills/pre-release-sweep/SKILL.md) over the range from the previous release tag to `main`, unless the release manager has already run it for this release and `main` has not moved since.
Do not draft the planning issue until the sweep's PR plan has been through its approval step.

Record in the planning issue, under a *Pre-release sweep* heading:

- the commit the sweep ran at;
- each fix PR it produced, as a link, with its state;
- the findings the release manager deferred past this release, each with its follow-up issue;
- the issues it closed or proposed to close.

Before Step 2 (`prep`) drafts the version-bump PR, check that every sweep PR the release manager marked release-blocking has merged, and that the sweep's spec-sync PR has merged, since a version bump ships what the specs describe ([`CONTRIBUTING.md` → Bumping the dev version](../CONTRIBUTING.md#bumping-the-dev-version)).
If one has not, stop and name it; the release manager decides whether to wait or to defer it.
