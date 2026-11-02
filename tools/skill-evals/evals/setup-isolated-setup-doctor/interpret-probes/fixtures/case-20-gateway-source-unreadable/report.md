<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Probe output collected in a project with no `.apache-magpie/` snapshot, whose gateway wiring lacks the read grant for the operator install.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: docker-runtime → ✗ (gateway status unavailable — gateway source at /Users/alice/.claude/scripts/container-gateway/src is not readable inside the sandbox — grant ~/.claude/scripts/container-gateway/ in sandbox.filesystem.allowRead; a socket exists at /Users/alice/tracker/.git/apache-magpie/run/main/docker.sock, but nothing confirms it is the gateway's)
