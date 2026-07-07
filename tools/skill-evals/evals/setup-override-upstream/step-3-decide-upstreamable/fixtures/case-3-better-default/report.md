<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Override file: `.apache-magpie-overrides/issue-triage.md`
Override content summary:
  # Override 1 — Change stale-detection default to 90 days
  The framework marks issues as potentially stale after 60 days
  without activity. This override changes that threshold to 90 days,
  which we have found is more appropriate for open-source projects
  with irregular contributor availability. Most projects we have
  discussed this with would also prefer 90 days.

Framework skill: `issue-triage`
Relevant section: "Step 2 — Detect stale issues"
The current default of 60 days was chosen arbitrarily. Feedback from
multiple adopters suggests 90 days is a better default, with the old
60-day threshold remaining available as a config option.
