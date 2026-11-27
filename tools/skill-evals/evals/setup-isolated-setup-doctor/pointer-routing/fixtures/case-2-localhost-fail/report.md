<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The harness is Claude Code. Every probe has run; this is its output, and the report is not written yet.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✗ (bind: [Errno 1] Operation not permitted)
PROBE: podman-runtime → ✓ (podman reaches the container gateway at /home/dev/proj/.apache-magpie-local/run/podman.sock)
PROBE: project-scratch → ✓ (writable; shared session root, which is the harness default: /tmp/claude-1000)
PROBE: signing-key → ✓ (readable inside sandbox)
PROBE: gh-sandbox → ✓ (gh works inside the sandbox)
PROBE: dev-tools → ✓ (found: prek, uv; ~/.cache writable)
PROBE: git-hooks → ✓ (/home/dev/.config/git/hooks readable; hooks visible: pre-commit)
PROBE: working-dirs → ✓ (/tmp/claude-1000 is a working directory)
