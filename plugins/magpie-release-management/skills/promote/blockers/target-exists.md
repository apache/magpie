<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Blocked — target URL already populated

**Likely cause:** a previous promote attempt partially landed, or a concurrent session already promoted the release.

**Remediation:** refuse and hand off to the RM with ASF Infra (Golden rule 4).
Never guess whether to overwrite or skip, and never emit a command that would.
The RM inspects `dist/release/<project>/<version>/` (`release_dist_backend = svnpubsub`) manually,
or the existing release for other backends (`gh release view <version>` for `github-releases`),
and contacts ASF Infra if the state is unclear.
