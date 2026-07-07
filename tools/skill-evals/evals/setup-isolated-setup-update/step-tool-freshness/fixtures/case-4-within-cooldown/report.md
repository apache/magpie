<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

tools/agent-isolation/check-tool-updates.sh output:

bubblewrap:
  pinned: 0.8.0
  latest: 0.8.0
  age_days: N/A (already at latest)
  status: UP-TO-DATE

socat:
  pinned: 1.7.4.4
  latest: 1.7.4.4
  age_days: N/A (already at latest)
  status: UP-TO-DATE

claude-code:
  pinned: 1.2.3
  latest: 1.2.4
  age_days: 3
  changelog: https://github.com/anthropics/claude-code/releases/tag/1.2.4
  status: NEWER VERSION AVAILABLE (within 7-day cooldown — check again in 4 days)

No candidates past cooldown. 1 tool has a newer version available but
is still within the framework's 7-day wait window.
