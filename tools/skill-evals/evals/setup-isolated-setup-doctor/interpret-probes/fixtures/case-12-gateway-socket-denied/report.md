<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Probe output collected after the operator forgot to add the gateway sockets to allowUnixSockets.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: podman-runtime → ✗ (connect to ./.apache-magpie-local/run/podman.sock denied — add it to sandbox.network.allowUnixSockets)
PROBE: docker-runtime → ✓ (docker reaches the container gateway at ./.apache-magpie-local/run/docker.sock)
