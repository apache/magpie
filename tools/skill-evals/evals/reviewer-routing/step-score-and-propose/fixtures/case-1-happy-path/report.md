<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR: apache/example#42
Title: "fix(scheduler): correct task-instance state after heartbeat timeout"
Author: contributor-alice
Labels: component:scheduler, kind:bug
Changed paths:
  example/jobs/scheduler.py
  example/jobs/heartbeat.py

Roster:
  - handle: maintainer-bob
    areas: [component:scheduler, component:triggerer]
    max_reviews: 5
    open_review_count: 2
  - handle: maintainer-carol
    areas: [component:dag-parsing, component:api]
    max_reviews: 5
    open_review_count: 1
  - handle: maintainer-dan
    areas: [component:scheduler]
    max_reviews: 5
    open_review_count: 3

Git-history familiarity (recent authors of changed paths):
  example/jobs/scheduler.py  → maintainer-bob (3 commits), maintainer-dan (1 commit)
  example/jobs/heartbeat.py  → maintainer-bob (2 commits)
