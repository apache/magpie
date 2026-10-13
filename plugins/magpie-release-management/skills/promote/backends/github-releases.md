<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Promotion backend — `github-releases`

The render's `command_block` publishes the draft GitHub Release (`gh release edit <draft-tag> --repo <upstream> --draft=false --tag <version>`)
and verifies it (`gh release view <version>`).
If the draft release was tagged `<version>-rc<N>`, the `--tag` flag re-tags it as `<version>` at publish time.

**Tag discrepancy.** Pass the tag the draft release actually carries as `--draft-tag <tag>`.
When it differs from `<version>-rc<N>`, the render refuses with the discrepancy instead of emitting the command:
surface it and ask the RM to confirm the correct tag name.
Only after the RM confirms, rerun with `--draft-tag <tag> --draft-tag-confirmed`.

The promotion event is the publish action (`--draft=false`); the mirror note's one-hour clock starts there.
