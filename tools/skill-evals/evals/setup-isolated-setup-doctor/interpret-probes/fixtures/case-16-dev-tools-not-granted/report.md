<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

All seven probes ran to completion on a Linux host whose worktree settings.local.json carries only the project root.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: project-scratch → ✓ (writable; shared session root, which is the harness default: /tmp/claude-1000)
PROBE: signing-key → ⊘ (gpg.format is not ssh)
PROBE: gh-sandbox → ✓ (gh works inside the sandbox)
PROBE: dev-tools → ⚠ (prek and uv not found; /home/alice/.local/bin is not in /home/alice/tracker/.claude/settings.local.json)
