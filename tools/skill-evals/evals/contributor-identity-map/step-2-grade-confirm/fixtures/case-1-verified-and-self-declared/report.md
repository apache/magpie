<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

context: standalone
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
existing_entry: none
reachable_tools: [gh, slack]
not_searched: [discord (no Discord tool connected)]
evidence:
  github-profile:
    social_accounts:
      - provider: mastodon
        url: https://fosstodon.org/@priya
  commit-metadata:
    emails: [priya@example.com]
  slack:
    - search: email priya@example.com
      hit: "@priya (U012ABCDEF)"
      profile_fields:
        GitHub: https://github.com/psharma-oss
