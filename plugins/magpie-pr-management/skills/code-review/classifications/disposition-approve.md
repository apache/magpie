<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Disposition `APPROVE`

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `disposition` picks it only when every gate holds: rollup `SUCCESS` with real CI (Golden rule 8), no unresolved review thread, no other maintainer's standing `CHANGES_REQUESTED`, no unanswered maintainer question (Golden rule 7), and no finding above `nit`.
Summary line: specific, never boilerplate — *"LGTM — clean N+1 fix with regression test, CI green."*
The maintainer may still downgrade it; an upgrade to `APPROVE` past a gate the tool named needs the maintainer to say why.
