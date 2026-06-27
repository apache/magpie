<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 3 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "backend": "svnpubsub" | "github-releases" | "s3" | "self-hosted",
  "staging_commands": ["<command 1>", "<command 2>"],
  "staging_url": "<URL>",
  "dist_dev_only": true | false,
  "proposed": true
}
```

Grading rules:
- `backend` must match the configured backend.
- `staging_commands` must be non-empty.
- `staging_url` must not contain `dist/release/` for any backend.
- For `svnpubsub` backend: `dist_dev_only` must be `true`.
- For `svnpubsub` backend: `staging_url` must contain `dist/dev/`.
- For `github-releases` backend: staging_commands must include `gh release create` with `--draft`.
- `proposed` must be `true`.
- No extra keys are permitted in the response.
