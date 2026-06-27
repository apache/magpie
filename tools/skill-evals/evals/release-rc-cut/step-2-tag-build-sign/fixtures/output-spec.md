<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "section_1_tag_commands": "<multi-line string: git tag -s + git push>",
  "section_2_build_command": "<string>",
  "section_3_sign_commands": ["<gpg --detach-sign --armor <artefact>>"],
  "section_4_checksum_commands": ["<sha512sum / sha256sum commands>"],
  "prohibited_digests_omitted": true,
  "proposed": true
}
```

Grading rules:
- `section_1_tag_commands` must include `git tag -s` with the version-rcN tag.
- `section_1_tag_commands` must include `git push` to push the tag.
- `section_2_build_command` must be the build command from the config.
- `section_3_sign_commands` must contain one `gpg --detach-sign --armor` per expected artefact.
- `section_3_sign_commands` must NOT include any passphrase argument.
- `section_4_checksum_commands` must contain `sha512sum` for each artefact.
- `section_4_checksum_commands` must contain `sha256sum` for each artefact when sha256 is in digest_set.
- `section_4_checksum_commands` must NOT contain `md5sum` or `sha1sum`.
- `prohibited_digests_omitted` must be `true`.
- `proposed` must be `true`.
- No extra keys are permitted in the response.
