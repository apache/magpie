<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: .claude/skills/issue-reassess/SKILL.md

wc -l SKILL.md: 372
Largest section: "## Step 2 — Reproduce" (61 lines) — within range.

Placeholder linter: clean.
In-context reads: none beyond the per-issue code the skill must reason over.
Per-item fetch loop: none — the pool is supplied upfront.
Pre-flight filter: ABSENT — the skill runs a full LLM reproduction pass on every pool issue, including issues closed-and-aged past the window and issues whose last activity is bot-only. A deterministic classifier could skip those obvious no-ops before the LLM pass.
