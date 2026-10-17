<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off — empty merged-PR set

**Likely cause:** no PRs were merged into `<release-branch-base>` since the previous release tag (Golden rule 3).

**Remediation:** report the empty set and hand off; do not draft a planning issue for an empty release.
The RM decides whether to skip the release, or reruns with `--skip-empty-check "<reason>"`;
the `plan` command then drafts the issue and logs the reason at the end of its body.
