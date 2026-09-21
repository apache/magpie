<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Probe output collected after wiring the container gateway hooks.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: podman-runtime → ✓ (podman reaches the container gateway at /Users/alice/tracker/.apache-magpie-local/run/podman.sock)
PROBE: docker-runtime → ⊘ (docker not on PATH)
