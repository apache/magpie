<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — `retention-rule-error`

`retention` printed `retention_rule_error: true`: the rule would archive the most-recent version of a supported train (a `keep` below 1).
`past_retention` is empty, `render` refuses, and no archival command may be emitted (Golden rule 2).

Set `handoff_required: true`, copy the `retention-rule-error: …` entries of `handoff_reasons`, and hand off to the RM:
archiving the latest release of a supported line is a user-visible regression and must be decided by a human.
The fix is `archive_retention_rule` in `<project-config>/release-management-config.md` (or the `keep` you derived from it).
