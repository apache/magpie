<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Every probe ran to completion. TMPDIR is the shared session root rather than a per-project directory, which is the harness default and not a finding: Claude Code sets TMPDIR itself when it builds the sandbox, overriding any env.TMPDIR from a settings file.

PROBE: ssh-agent → ✓ (1 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: project-scratch → ✓ (writable; shared session root, which is the harness default: /tmp/claude-501)
PROBE: signing-key → ⊘ (gpg.format is not ssh)
PROBE: gh-sandbox → ✓ (gh works inside the sandbox; exclusion not needed on this platform)
