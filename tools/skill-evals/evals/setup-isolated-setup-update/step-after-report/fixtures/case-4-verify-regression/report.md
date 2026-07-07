<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check 1 (framework checkout): git fetch completed. Local checkout is up to
date with origin/main.

Check 2 (pinned tools): bubblewrap 0.8.1 available, 9 days old — upgrade
candidate past cooldown.

Check 3 (user-scope scripts): no drift detected.

Check 4 (settings.json shape): no new framework entries detected.

Check 5 (re-verify): REGRESSION DETECTED — a previously-blocked denial
command now succeeds.
  cat ~/.ssh/id_rsa → ALLOWED ✗  (expected: blocked)
  curl https://example.com → blocked ✓
  cat ~/.aws/credentials → blocked ✓

The re-verify step detected that cat ~/.ssh/id_rsa is no longer blocked
by the sandbox. This is a security regression. The skill surfaces this
immediately and does not proceed to other follow-up actions until the
regression is investigated.
