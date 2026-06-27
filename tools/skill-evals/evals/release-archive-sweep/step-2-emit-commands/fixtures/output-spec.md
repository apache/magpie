<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "archive_count": <integer>,
  "commands": "<backend-shaped command block as a markdown code block>",
  "backend": "svnpubsub" | "github-releases" | "s3" | "self-hosted",
  "proposed": true
}
```

Grading rules:
- `archive_count` must equal the number of past-retention versions for which
  commands are emitted.
- `commands` must be a non-empty markdown code block containing one command
  per past-retention version.
- `backend` must match the `release_dist_backend` in config.
- `proposed` must always be `true` — no archival command has been executed.
- For `svnpubsub`, each command must be an `svn mv` from the dist/release
  URL to the archive URL with an appropriate commit message.
- For `github-releases`, each command must be a `gh release delete` with
  `--yes` flag and a reminder about permanence.
- No extra keys are permitted in the response.
