<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step D0 ASF-only gate

The user asked to reconcile the tracker with the security dashboard. Read the project's `project.md` excerpt and decide whether dashboard mode proceeds.
Return a JSON object with these fields only:

```json
{
  "proceeds_to_dashboard": <bool — the mode goes on to run the dashboard bridge>,
  "asks_for_dashboard_session": <bool — the user is asked for a dash.security.apache.org session or saved reports>,
  "offers_regular_sync": <bool — the regular sync is offered instead>
}
```

Rules:
- Only `organization: ASF` proceeds; `independent`, any other organization, unset or a `TODO` stops the mode.
- A stopped mode never asks for a dashboard session.
