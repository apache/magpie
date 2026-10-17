<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Promotion backend — `github-releases`

The render's `command_block` publishes the draft GitHub Release (`gh release edit <draft-tag> --repo <upstream> --draft=false --prerelease=false --tag <version>`)
and verifies it (`gh release view <version>`).
`release-rc-cut` creates the draft with `--prerelease`, so `--prerelease=false` is what makes the published release a full release rather than a prerelease.
A held convenience artefact attached to the draft is deleted first, with its `.asc` and its `.<digest>` assets (`gh release delete-asset <draft-tag> <name> --repo <upstream> --yes &&` each), so the publish never ships it;
see [`../convenience-artefacts.md`](../convenience-artefacts.md).
If the draft release was tagged `<version>-rc<N>`, the `--tag` flag re-tags it as `<version>` at publish time.

**Tag discrepancy.** Pass the tag the draft release actually carries as `--draft-tag <tag>`;
it is required for this backend, and the render refuses without it (read it with `gh release list --repo <upstream>`).
When it differs from `<version>-rc<N>`, the render refuses with the discrepancy instead of emitting the command:
surface it and ask the RM to confirm the correct tag name.
Only after the RM confirms, rerun with `--draft-tag <tag> --draft-tag-confirmed`.

The promotion event is the publish action (`--draft=false`); the mirror note's one-hour clock starts there.
