<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

context: onboarding
record: true
contributor:
  github: psharma-oss
  name: Priya Sharma
configured_channels:
  - id: slack
    label: ASF Slack
    workspace: the-asf.slack.com
  - id: discord
    label: Project Discord
existing_entry:
  github: psharma-oss
  channels:
    slack:
      handle: "@priya"
      id: U012ABCDEF
      grade: verified
  confirmed_by: jmclean
  confirmed_on: 2026-03-02
reachable_tools: [gh, slack, discord]
evidence:
  discord:
    - search: name "Priya Sharma"
      hits:
        - handle: priya.sharma
          connected_accounts:
            github: psharma-oss
