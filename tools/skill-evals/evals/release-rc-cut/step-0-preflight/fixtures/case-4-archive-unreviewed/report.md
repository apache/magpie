<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-rc-cut 1.0.0 rc1   (no --allow-unreviewed-archive)

Planning issue: apache/foo#12 (open, labelled `release-planning`,
title "Release Apache Foo 1.0.0" — the project's first release)
Planning issue body excerpt:
  Prep PR: apache/foo#11 — MERGED (label prep-pr-open absent)
  No RC tag exists yet for 1.0.0-rc1.

RC tag check: vetted-op-read tags 1.0.0-rc1 → (no output)

Root .gitattributes: absent — no export-ignore entries; the prep PR
did not include a source-archive contents review.

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill rc-cut 1.0.0 rc1`):

```json
{
  "ok": false,
  "skill": "rc-cut",
  "blockers": [
    "export_ignore_reviewed is unset in release-build.md § Source archive (archive_reviewed: false): run `release-prepare prep 1.0.0` — its Step 2f walks you through what ships in the source archive and lands `.gitattributes` in the prep PR"
  ],
  "warnings": [],
  "values": {
    "version": "1.0.0",
    "rc_number": "rc1",
    "archive_reviewed": false,
    "allow_unreviewed_archive": false,
    "signing_mode": "rm-key",
    "staging_url": "https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/",
    "rc_tag": "1.0.0-rc1"
  }
}
```
