<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Probe output collected while the gateway is up but the Podman machine is stopped.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: podman-runtime → ✗ (gateway running without a podman backend — is the Podman machine started? start it, then restart the gateway)
PROBE: docker-runtime → ✓ (docker reaches the container gateway at /Users/alice/tracker/.apache-magpie-local/run/docker.sock)
