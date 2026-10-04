<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare 0.9.3
Project: Velox Stream (non-ASF, github-releases backend)

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill prepare 0.9.3`):

```json
{
  "ok": true,
  "skill": "prepare",
  "blockers": [],
  "warnings": [],
  "values": {
    "sub_command": "plan",
    "version": "0.9.3",
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

gh pr list access confirmed: velox-community/velox-stream responds with merged PRs.
Previous release tag detected: 0.9.2

No svnpubsub. No vote mailing list. No announce@apache.org.
No .apache-magpie.local.lock drift.
No .apache-magpie-overrides/release-prepare.md found.
