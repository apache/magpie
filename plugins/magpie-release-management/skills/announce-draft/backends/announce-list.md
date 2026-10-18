<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Announce backend — `announce-list` (ASF)

The only legal value for an ASF project (Golden rule 7).
The render's `body` is the `[ANNOUNCE]` email, ready to paste into the RM's mail client:

- `To: <announce_list>`, `Cc: <announce_cc_lists joined by ", ">`, `Subject:` — the header block.
- **The `@apache.org` sender reminder** — always present (Golden rule 4); `asf_address_reminder_present` is `true`.
  A `canned_body` without it gets it prepended, and `reminder_prepended` says so.
- The Download Page, the release notes / changelog and the `KEYS` URL, each on its own line.
- **Convenience artefacts** — only when `release-build.md § Convenience artefacts` declares any that `release-promote` published:
  pass one `--convenience <kind>=<publish_channel location>` per published artefact (e.g. `wheel=https://pypi.org/project/<name>/<version>/`),
  read from the promote hand-back; a held artefact is not announced.
- `--dev-list` / `--users-list` from `project.md` → *Mailing lists*, and `--description`, one sentence from the planning issue or config;
  each stays a placeholder when not found, for the RM to fill in.
- **`[SKIP-PROMOTE-WAIT: …]`** — only with `--skip-promote-wait <reason>`; the reason is logged in the body.

**Download Page, not `dist.apache.org`** (Golden rule 5).
`download_page_is_dist: true` comes with a warning: ask the RM for the project's Download Page URL, rerun with `--download-page <url>`, and only then finalise the body.
The Download Page serves the CDN/mirror selector (`closer.lua`).
