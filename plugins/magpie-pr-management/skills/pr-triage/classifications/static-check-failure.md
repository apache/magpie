<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `deterministic_flag` → `comment` — rows 12 and 12b, static-check failure

**Fires when** CI failure is the only signal and every failed check (row 12) or any failed check (row 12b) is a static check: lint, formatting, type checking, spelling, docs build, or a pattern from `static_check_patterns`.
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `details.failed_checks` lists the failures.

**Proposed action:** `comment` with the violations body — [`actions/comment.md`](../actions/comment.md).

## Why

These failures are deterministic; rerunning will not help.
The author needs to fix and push, and a comment closes the loop in one round-trip — no reason to draft.
Row 12b exists because a rerun would re-fail on the static check even when other failures are flakes.
The docs-build and spellcheck patterns are static checks for the same reason: the contributor introduced text the checker does not accept, and the fix is a code change.
