<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

User invocation: /setup-override-upstream

Directory scan results:
- `.apache-magpie.lock` found at repo root.
- `.apache-magpie-overrides/` directory found at repo root.
- `.apache-magpie.local.lock` found at repo root (gitignored).

Committed lock (`.apache-magpie.lock`):
  method: svn-zip
  url:    https://dist.apache.org/repos/dist/release/magpie/magpie-1.0.0.zip
  ref:    1.0.0
  sha512: aabbccdd11223344aabbccdd11223344aabbccdd11223344aabbccdd11223344aabbccdd11223344aabbccdd11223344aabbccdd11223344aabbccdd11223344

Local lock (`.apache-magpie.local.lock`):
  source_method: svn-zip
  source_url:    https://dist.apache.org/repos/dist/release/magpie/magpie-1.0.0.zip
  source_ref:    1.0.0
  fetched_sha512: 99887766554433229988776655443322998877665544332299887766554433229988776655443322998877665544332299887766554433229988776655443322
  fetched_at:    2026-05-01T08:00:00Z

SHA-512 mismatch: committed anchor does not match the locally fetched zip's hash.
