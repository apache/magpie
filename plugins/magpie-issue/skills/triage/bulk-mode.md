<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Bulk mode for N > 5

Companion to [`SKILL.md`](SKILL.md). The subagent-fanout pattern used by
Step 2 when the resolved selector has more than five issues, and the hard
rules that govern it.

**Bulk mode for N > 5** — when the resolved selector has more
than 5 issues, follow the same subagent-fanout pattern as
[`security-issue-triage`](../../../magpie-security/skills/issue-triage/SKILL.md): one
read-only subagent per issue, all spawned in a single message,
each returning a structured per-issue report that the orchestrator
aggregates.

**Hard rules for bulk mode**:

- Subagents are read-only; they never call any write tool on the
  tracker.
- Subagents do not classify or propose; the orchestrator does
  Step 3 + Step 4 from the aggregated state. (Classification is
  a single-context decision; deferring it to subagents would let
  inconsistent reads slip past.)
- The orchestrator runs the apply phase (Step 6) sequentially,
  one comment per issue, never in parallel.
