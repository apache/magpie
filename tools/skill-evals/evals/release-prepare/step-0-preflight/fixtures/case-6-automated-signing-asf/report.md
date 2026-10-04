<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-prepare automated-signing
Project: Apache Foo (project.md → organization: ASF)

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill prepare automated-signing`):

```json
{
  "ok": true,
  "skill": "prepare",
  "blockers": [],
  "warnings": [],
  "values": {
    "sub_command": "automated-signing",
    "version": null,
    "release_branch_base": "main",
    "previous_tag": null,
    "release_lines": [
      "**`main`** — the 3.x train, Release Manager @jdoe."
    ],
    "organization": "ASF",
    "automated_signing_offered": true
  }
}
```

release-build.md: source_archive_method git-archive, reproducibility_source: on,
  reproducibility_binaries: byte-identical (one convenience binary).
gh pr list access confirmed: apache/foo responds.
No .apache-magpie.local.lock drift. No override file.
