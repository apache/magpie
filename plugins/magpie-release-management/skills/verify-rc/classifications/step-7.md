<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 7 — Source-tree integrity

From `release-verify symlinks`, with `REVIEW` resolved by `release-management verify-rc source-tree`.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 7 FAIL — dangling symlink | A committed symlink's target was stripped by `export-ignore` (or is otherwise absent) | RM fixes `.gitattributes` to ship the target (or drops the symlink), cuts new RC |
| Step 7 FAIL — symlink resolves outside the archive | A committed symlink is absolute or climbs out of the tree with `..` | RM replaces it with a relative link to shipped content (or drops it), cuts new RC |
| Step 7 FAIL — broken internal reference | A shipped file links to a path stripped from the artefact | RM stops stripping the referenced path, or repoints the reference at shipped content, cuts new RC |
| Step 7 SKIP — no validators declared | `release-build.md § Source-tree validators` is empty | Fine for a project with no in-tree link or symlink checks; declare the project's own validators if it has them |
