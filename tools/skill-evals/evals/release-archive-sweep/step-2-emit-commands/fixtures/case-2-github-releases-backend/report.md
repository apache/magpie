<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (non_asf: true)
Step 1 result:
  dist_backend: github-releases
  releases_found: [1.0.0, 1.1.0, 1.2.0]
  past_retention: [1.0.0, 1.1.0]
  orphans: []
  latest_of_each_line: {"1.x": "1.2.0"}
  handoff_required: false

Config:
  project_dist_name: myproject
  release_dist_backend: github-releases
  upstream: example-org/myproject
  archive_retention_rule: keep latest of each supported train only
  NOTE: github-releases backend — deletion is permanent, no separate archive area.
