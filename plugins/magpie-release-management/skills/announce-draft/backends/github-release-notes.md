<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Announce backend — `github-release-notes` (`non_asf`)

The render's `body` is a GitHub Release page body: no `To:` / `Cc:` header, markdown prose, a `## Downloads` section (Download Page, `KEYS` when configured, convenience artefacts) and a `## Changelog` section.
There is no `@apache.org` sender reminder: `asf_address_reminder_present` is `false`.
The RM pastes it into the release on GitHub; the skill never edits the release itself.
