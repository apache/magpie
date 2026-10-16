<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-scan — the skills it composes with

It composes with:

- [`security-issue-import`](../../issue-import/SKILL.md) — the
  Gmail on-ramp; this skill reuses its Step 2a fuzzy-dup search, its
  reject-pattern check, and its Step 7 tracker-creation path.
- [`security-issue-triage`](../../issue-triage/SKILL.md) — whose
  Security-Model trust-boundary cheat-sheet and closed-invalid /
  positive-precedent searches do the actual classification.
- [`security-issue-fix`](../../issue-fix/SKILL.md) — where a
  confirmed PR-worth finding becomes a public hardening PR.
