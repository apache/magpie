<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Scope violation — a proposed file outside the expected set

**Likely cause:** the diff touches a file the step does not own:
for `prep`, outside the 2f file set; for `post`, outside `version_manifest_files` (Golden rule 5).

**Remediation:** surface each `scope_violations` entry and ask the RM to confirm it before including it;
rerun the render with `--confirm-extra <file>` for each one the RM confirms, or drop it from the diff.
`NOTICE` and `LICENSE` are never part of the post-release bump: `post-pr` refuses to confirm them.
