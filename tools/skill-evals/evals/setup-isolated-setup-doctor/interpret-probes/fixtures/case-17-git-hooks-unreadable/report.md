<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

All eight probes ran to completion on a Linux host in whole-user scope (global core.hooksPath) with no sandbox grant for the hook dir.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: project-scratch → ✓ (writable; shared session root, which is the harness default: /tmp/claude-1000)
PROBE: signing-key → ⊘ (gpg.format is not ssh)
PROBE: gh-sandbox → ✓ (gh works inside the sandbox)
PROBE: dev-tools → ✓ (found: prek uv; /home/alice/.cache writable)
PROBE: git-hooks → ✗ (core.hooksPath /home/alice/.claude/git-hooks not readable inside sandbox; sandboxed git skips every hook)
