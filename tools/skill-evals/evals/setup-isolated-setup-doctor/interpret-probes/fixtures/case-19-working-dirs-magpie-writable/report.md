<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

All nine probes ran to completion on a Linux host whose project-local settings still list the vetted-ops checkout as a working directory, as an older sandbox-add-project-root.sh wrote it.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: project-scratch → ✓ (writable; shared session root, which is the harness default: /tmp/claude-1000)
PROBE: signing-key → ⊘ (gpg.format is not ssh)
PROBE: gh-sandbox → ✓ (gh works inside the sandbox)
PROBE: dev-tools → ✓ (prek and uv found and writable)
PROBE: git-hooks → ⊘ (core.hooksPath not set; per-project scope)
PROBE: working-dirs → ✗ (/home/alice/.claude/magpie is a working directory overlapping /home/alice/.claude/magpie, so sandboxed commands can write the vetted-ops checkout; remove it from additionalDirectories — sandbox-add-project-root.sh --all-worktrees removes the ~/.claude/magpie entry it once added, any other needs a hand edit)
