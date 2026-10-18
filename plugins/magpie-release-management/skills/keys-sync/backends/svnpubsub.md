<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# KEYS backend — `svnpubsub` (`dist.apache.org`)

`svn_command_sequence` checks out only the KEYS-file directory (`keys_file_url` with `/KEYS` stripped, `--depth immediates`) into `/tmp/<project-dist-name>-keys`,
leaves the append of `keys_block_to_append` to the RM, and commits KEYS with `-m "Add <rm-uid> to KEYS (fingerprint: <fingerprint>)"`.

**`KEYS` belongs in `dist/release`, never `dist/dev`.**
The file is long-lived project metadata, not a release artefact, and voters and future verifiers fetch it from the released location.
`keys_file_url` should always resolve under `dist/release/<project>/KEYS`.
A `dist/dev` URL, or one not ending in `/KEYS`, is refused by the render: treat that as a configuration error and say so rather than emitting a command against it.
