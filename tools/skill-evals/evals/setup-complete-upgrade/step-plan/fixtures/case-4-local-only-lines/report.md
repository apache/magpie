<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Personal layer: `.apache-magpie-local/`. Isolated setup: configured.

Findings:
- slug: sandbox-status-line-local-edits. `~/.claude/scripts/sandbox-status-line.sh` differs from the framework copy.
  The diff shows 4 lines present in the user-scope copy that the framework copy does not have (a local colour theme and a custom prompt segment), plus one line the framework copy added since.
  Diff written to `$TMPDIR/sandbox-status-line.diff`.
