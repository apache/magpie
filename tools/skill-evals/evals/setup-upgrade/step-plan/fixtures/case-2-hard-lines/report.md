<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code (sandboxed Bash; `dangerouslyDisableSandbox` available).
Personal layer: `.apache-magpie-local/` (main checkout, adopted project). Isolated setup: configured.

Findings:
- slug: vetted-ops-policy-tracker-table. The vetted-ops policy at `.apache-magpie-overrides/tools/vetted-ops/policy.toml` lacks a `[tracker]` table the new version expects.
- slug: committed-settings-missing-deny. The committed `.claude/settings.json` lacks a deny rule the framework template now carries.
- slug: uv-toml-cache-dir. Verifying `cache-dir` in `~/.config/uv/uv.toml` needs reading that file, which is a credential-set path.
- slug: lock-stamp-stale. The `reconciled:` block in the committed `.apache-magpie.lock` is behind the installed version (`fingerprint-moved`).
