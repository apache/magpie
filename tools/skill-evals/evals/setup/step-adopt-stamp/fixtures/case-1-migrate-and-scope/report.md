<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This is a re-adoption. Step 2's floor diff kept `min_version: 0.4.0` in
the lock (the existing floor was already higher than what this machine
has installed, so Step 2 left it there per the never-lower rule).

The version Step 2 actually read off this machine via
`claude plugin list --json`: 0.3.1.

`.apache-magpie-local/reconciled.json`, read before this step:
  version: 0.2.0
  at:      2026-08-01
  skills:
    magpie-issue-triage: sha256:aaaaaaaaaaaaaaaa
  verified_at:            2026-09-10
  acknowledged:            (empty)

4a promoted `.apache-magpie-local/naming-conventions.md` to
`.apache-magpie-overrides/naming-conventions.md` for
`magpie-pr-management-code-review`, whose current `surface_hash` (from
its `SKILL.md` frontmatter, already in context) is
sha256:1d0038ec4fde60bf. 4b and 4c found nothing else to do.

Today: 2026-09-21
