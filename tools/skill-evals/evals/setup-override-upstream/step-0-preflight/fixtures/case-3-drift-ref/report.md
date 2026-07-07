<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

User invocation: /setup-override-upstream

Directory scan results:
- `.apache-magpie.lock` found at repo root.
- `.apache-magpie-overrides/` directory found at repo root.
- `.apache-magpie.local.lock` found at repo root (gitignored).

Committed lock (`.apache-magpie.lock`):
  method: git-tag
  url:    https://github.com/apache/magpie.git
  ref:    v1.2.0
  commit: deadbeef1234

Local lock (`.apache-magpie.local.lock`):
  source_method: git-tag
  source_url:    https://github.com/apache/magpie.git
  source_ref:    v1.1.0
  fetched_commit: cafe5678abcd
  fetched_at:    2026-04-10T14:30:00Z

Drift detected: committed ref is v1.2.0; local snapshot is at v1.1.0.
