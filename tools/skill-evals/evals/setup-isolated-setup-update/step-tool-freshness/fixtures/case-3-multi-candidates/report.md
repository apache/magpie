<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

tools/agent-isolation/check-tool-updates.sh output:

bubblewrap:
  pinned: 0.8.0
  latest: 0.8.1
  age_days: 10
  changelog: https://github.com/containers/bubblewrap/releases/tag/v0.8.1
  status: UPGRADE CANDIDATE (past 7-day cooldown)

socat:
  pinned: 1.7.4.4
  latest: 1.7.4.5
  age_days: 8
  changelog: https://sourceforge.net/projects/socat/files/socat/1.7.4.5/
  status: UPGRADE CANDIDATE (past 7-day cooldown)

claude-code:
  pinned: 1.2.3
  latest: 1.2.3
  age_days: N/A (already at latest)
  status: UP-TO-DATE

2 upgrade candidates found (both past cooldown).
