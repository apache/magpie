<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "keys_block_to_append": "<# comment line + armoured key block>",
  "svn_command_sequence": "<paste-ready multi-line command string>",
  "keyserver_upload_reminder": "<string>",
  "proposed": true
}
```

Grading rules:
- `keys_block_to_append` must begin with a `# <uid>` comment line followed by
  a `-----BEGIN PGP PUBLIC KEY BLOCK-----` header.
- `keys_block_to_append` must end with `-----END PGP PUBLIC KEY BLOCK-----`.
- `svn_command_sequence` must contain checkout and commit commands appropriate
  for the backend (svn for dist.apache.org URLs, git for github.com URLs).
- `keyserver_upload_reminder` must be a non-empty string identifying the
  keyserver upload URL or upload instructions.
- `proposed` must always be `true`.
- No extra keys are permitted in the response.
