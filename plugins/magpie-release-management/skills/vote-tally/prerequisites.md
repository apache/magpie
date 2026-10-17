<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-vote-tally — prerequisites

- **Vote window has elapsed** — `vote_window_hours` (or `approval_window_hours` for non-list mechanisms) since the `[VOTE]` thread opened, **or** `--force-close <reason>` was passed.
- **Planning issue open** and labelled `vote-open` (or the RM provides its URL explicitly).
- **`<project-config>/release-management-config.md` readable** — `release_approval_mechanism`, `vote_window_hours`, `result_subject_template`, and optionally `release_approver_roster_path` (default `<project-config>/pmc-roster.md`).
- **Approver roster readable** at `<release-approver-roster>`.
- **Approval signal available** — PonyMail thread, GitHub Discussion, PR reviews, or maintainer-roster file, depending on `release_approval_mechanism`.
