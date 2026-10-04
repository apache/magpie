<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare automated-signing
Project: Velox Stream (project.md → organization: independent; github-releases backend)

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill prepare automated-signing`):

```json
{
  "ok": false,
  "skill": "prepare",
  "blockers": [
    "automated release signing is not offered by this project's organization (independent): release_process.automated_signing is unset or null (<framework>/organizations/independent/organization.md)"
  ],
  "warnings": [],
  "values": {
    "sub_command": "automated-signing",
    "version": null,
    "release_branch_base": "main",
    "previous_tag": null,
    "release_lines": [
      "**`main`** — the 0.x train; next release `0.9.3`, Release Manager @alex-velox."
    ],
    "organization": "independent",
    "automated_signing_offered": false
  }
}
```

gh pr list access confirmed.
No .apache-magpie.local.lock drift. No override file.
