<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

context: standalone
record: true
contributor:
  github: tkowalski
  name: Tomasz Kowalski
configured_channels:
  - id: slack
    label: ASF Slack
    workspace: the-asf.slack.com
  - id: discord
    label: Project Discord
existing_entry: none
reachable_tools: [gh, slack, discord]
evidence:
  github-profile:
    social_accounts: []
  commit-metadata:
    emails: [tkowalski@users.noreply.github.com]
  slack:
    - search: name "Tomasz Kowalski"
      hits: []
  discord:
    - search: name "Tomasz Kowalski"
      hits:
        - handle: tomek_k
          profile_links: none
        - handle: tkowal.dev
          profile_links: none
