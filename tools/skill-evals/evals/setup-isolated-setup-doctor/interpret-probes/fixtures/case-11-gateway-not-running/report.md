<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Probe output collected before the SessionStart hook had a chance to run.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: podman-runtime → ✗ (gateway socket missing at /Users/alice/tracker/.apache-magpie-local/run/podman.sock — container gateway not running)
PROBE: docker-runtime → ⊘ (docker not on PATH)
