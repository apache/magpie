<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

An older install left a project-relative CONTAINER_HOST in the committed .claude/settings.json. The gateway is running and the socket exists, but the CLI never reaches it: a unix:// URL's authority is read as a host component.

PROBE: ssh-agent → ✓ (1 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: podman-runtime → ✗ (CONTAINER_HOST=unix://./.apache-magpie-local/run/podman.sock is not absolute — the CLIs do not resolve a relative unix:// value against the cwd; use unix:///<project>/.apache-magpie-local/run/podman.sock)
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: project-scratch → ✓ (writable; shared session root, which is the harness default: /tmp/claude-501)
PROBE: signing-key → ⊘ (gpg.format is not ssh)
PROBE: gh-sandbox → ✓ (gh works inside the sandbox; exclusion not needed on this platform)
