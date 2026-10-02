<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

context: nomination
record: true
contributor:
  github: mchen
  name: Mei Chen
configured_channels:
  - id: slack
    label: ASF Slack
    workspace: the-asf.slack.com
  - id: linkedin
    label: LinkedIn
existing_entry: none
reachable_tools: [gh, slack]
evidence:
  github-profile:
    email: mei@example.org
    social_accounts: []
  slack:
    - search: email mei@example.org
      hit: "@mei (U09XYZ1234)"
  linkedin: no source reachable
