<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Candidate (surfaced by a backlog-grooming pass):

Proposed title: Design the plugin extension-point API
Description: We want third parties to register plugins, but we have not
decided the API shape: whether plugins register via entry points, a
decorator, or a config file; what the lifecycle hooks are; and how
version compatibility works. Decide the approach and implement it.
max_effort_hours: 4
Named source files:
  - none yet — depends on the design chosen
Acceptance notes: a plugin registration API exists.
