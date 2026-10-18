<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-vote-draft — prerequisites

- **`release-verify-rc` ran with PASS** on `<version>-<rcN>`, or `--skip-verify-check <reason>` was passed (Golden rule 5).
- **Planning issue open** and labelled `rc-staged`, or the RM gives its URL.
- **`<project-config>/release-management-config.md` readable** — `vote_window_hours`, `vote_subject_template`, `vote_dev_list`.
- **RC metadata available** — staging, tag, KEYS and changelog URLs, from the planning issue body or supplied explicitly.
