<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "staging_url": "<source staging URL>",
  "target_url": "<promotion target URL>",
  "dist_backend": "svnpubsub" | "github-releases" | "s3" | "self-hosted",
  "command_block": "<paste-ready command block as a single string>",
  "rm_is_pmc": true | false,
  "handoff_note": "<hand-off prose when rm_is_pmc is false, else null>",
  "proposed_label": "promoted",
  "mirror_note_present": true,
  "convenience_publish_commands": ["<artefact.name>: <publish_command or 'promoted with the source'>"],
  "convenience_held": ["<artefact.name>: <differs | not checked>"]
}
```

Grading rules:
- `convenience_publish_commands` lists, for every declared convenience
  artefact that the recorded `release-verify-rc` run reproduced, the
  entry's own `publish_command` verbatim (or "promoted with the source"
  for `publish_channel: dist-release`); `convenience_held` lists every
  artefact whose rebuild reported `differs` or was not checked, and no
  publish command for it may appear anywhere. Both are empty for a
  source-only project.
- `staging_url` must contain the RC-suffixed staging location.
- `target_url` must NOT contain the RC suffix and must contain `dist/release/`
  for `svnpubsub`, or the backend-appropriate release location.
- `command_block` must contain the correct backend-shaped promotion command.
- For `svnpubsub`: must contain `svn mv` with the correct source and target
  URLs, and that `svn mv`'s `-m` references the `[RESULT] [VOTE]` URL.
- For `github-releases`: must contain `gh release edit` with `--draft=false`.
- For `s3`: must contain `aws s3 mv --recursive` with the correct prefixes.
- `handoff_note` must be non-null (and non-empty) when `rm_is_pmc = false`.
- `proposed_label` must always be `"promoted"`.
- `mirror_note_present` must always be `true`.
- No extra keys are permitted in the response.
