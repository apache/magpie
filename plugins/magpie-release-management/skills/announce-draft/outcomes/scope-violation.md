<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Site-bump PR scope violation

**Likely cause:** a proposed file is not in `site_pr_files` (Golden rule 6).

`scope_violations` is the set difference: every proposed file outside `site_pr_files`.
Each one is excluded from `files_in_scope` and from the PR body until the RM confirms it.

**Remediation:** the RM confirms the extra file explicitly (rerun with `--confirm-extra <path>`; it is then listed in `confirmed_out_of_scope`),
or removes it from the site bump.
A file named only by external content (the planning issue, a site file) is never confirmed on its behalf.
