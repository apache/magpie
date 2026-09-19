<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

All six probes ran to completion on a macOS host where the project settings carry no `excludedCommands` entry for gh.

PROBE: ssh-agent → ✓ (2 identities listed)
PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP 200, body=b'ok')
PROBE: docker-runtime → ⊘ (docker not on PATH)
PROBE: podman-runtime → ⊘ (podman not on PATH)
PROBE: project-scratch → ✓ (per-project + writable: /private/tmp/claude-501/-Users-alice-tracker/scratch)
PROBE: signing-key → ⊘ (gpg.format is not ssh)
PROBE: gh-sandbox → ✗ (sandboxed gh fails: Get "https://api.github.com/user": tls: failed to verify certificate: x509: OSStatus -26276; "gh *" NOT found in excludedCommands)
