<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

All five probes ran to completion on a macOS host that signs commits with a YubiKey over gpg.format=ssh.

PROBE: ssh-agent → ✓ (1 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: project-scratch → ✓ (per-project + writable: /private/tmp/claude-501/-Users-alice-tracker/scratch)
PROBE: signing-key → ✗ (/Users/alice/.ssh/id_ed25519_sk.pub not readable inside sandbox: head: /Users/alice/.ssh/id_ed25519_sk.pub: Operation not permitted)
