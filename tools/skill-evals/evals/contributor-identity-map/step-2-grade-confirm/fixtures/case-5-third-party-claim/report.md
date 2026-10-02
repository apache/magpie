<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

context: standalone
record: true
contributor:
  github: psharma-oss
  name: Priya Sharma
configured_channels:
  - id: discord
    label: Project Discord
existing_entry: none
reachable_tools: [gh]
not_searched: [discord (no Discord tool connected)]
evidence:
  contributor-text:
    - author: another-maintainer   # not the contributor
      where: issue comment
      text: "FYI @psharma-oss is priya_s on the project Discord."
