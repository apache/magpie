<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

All nine probes ran to completion on a Linux host whose user-scope settings turn on the read block and list the scratch root as a glob.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: project-scratch → ✓ (writable; shared session root, which is the harness default: /tmp/claude-1000)
PROBE: signing-key → ⊘ (gpg.format is not ssh)
PROBE: gh-sandbox → ✓ (gh works inside the sandbox)
PROBE: dev-tools → ✓ (prek and uv found and writable)
PROBE: git-hooks → ⊘ (core.hooksPath not set; per-project scope)
PROBE: working-dirs → ⚠ (not a working directory: /tmp/claude-1000; the glob entry "/tmp/claude-*" is never matched)
