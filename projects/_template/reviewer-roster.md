<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — reviewer roster](#todo-project-name--reviewer-roster)
  - [Roster](#roster)
  - [Notes](#notes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — reviewer roster

Used by the [`reviewer-routing`](../../skills/reviewer-routing/SKILL.md) skill
to score and propose reviewers for inbound issues and PRs. Fill in each
maintainer's GitHub handle, the areas or file-path patterns they cover,
and optionally a `max_reviews` cap (default: 5).

For **ASF projects**, this file is optional — `reviewer-routing` also
reads area-to-handle mappings from `release-trains.md`. Use this file to
supplement or override those mappings, or to add non-committer reviewers
(e.g. regular contributors who review a specific area).

## Roster

<!--
Shape per entry:
  - handle: github-login        # GitHub @handle (required)
    areas:                      # list of areas / path prefixes / labels
      - component:scheduler
      - airflow/jobs/
    max_reviews: 5              # optional; default 5
-->

- handle: TODO-maintainer-1
  areas:
    - TODO-area-1
    - TODO-path-prefix-1/
  max_reviews: 5

- handle: TODO-maintainer-2
  areas:
    - TODO-area-2
  max_reviews: 5

## Notes

- `areas` entries may be component labels (e.g. `component:scheduler`),
  path prefixes (e.g. `airflow/jobs/`), or free-form area names that
  match the labels used in this project's issue tracker.
- `max_reviews` is the maximum number of open review requests this
  reviewer is comfortable holding simultaneously. When their current
  count meets or exceeds this value, `reviewer-routing` marks them
  `OVERLOADED` and excludes them from the primary suggestion slot.
- Keep this file up to date as maintainers rotate; stale entries cause
  the skill to propose inactive reviewers.
