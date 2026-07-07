<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check 1 (framework checkout): git fetch completed. Local checkout is 3
commits behind origin/main. Changes since last pull include:
  tools/agent-isolation/agent-iso.sh — 2 lines updated (new deny path)
  docs/setup/secure-agent-setup.md — 1 section added (Step P.0 clarification)

Snapshot drift check: .apache-magpie.lock ref is v0.9.5 but
.apache-magpie.local.lock ref is v0.9.4. Sync needed.

Check 2 (pinned tools): all tools are at their pinned versions. No upgrade
candidates.

Check 3 (user-scope scripts): no drift detected. All scripts match the
framework source-of-truth at the current local checkout ref.

Check 4 (settings.json shape): no new framework entries detected.

Check 5 (re-verify): denial commands all blocked as expected.
  cat ~/.ssh/id_rsa → blocked ✓
  curl https://example.com → blocked ✓
  cat ~/.aws/credentials → blocked ✓
