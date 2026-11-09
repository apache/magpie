<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Marketplace install; no framework git history is readable inside the sandbox. Personal layer: `<git-common-dir>/apache-magpie/`. Isolated setup: configured.

Findings:
- slug: bypass-warn-differs. `~/.claude/scripts/sandbox-bypass-warn.sh` differs from the framework copy materialised for the installed version.
  The diff shows 1 line present in the user-scope copy that the framework copy lacks, and 2 lines the framework copy has that the user-scope copy lacks.
  No history is available to tell whether the extra line is a local edit or a line upstream removed. The framework copy carries no known security fix.
  Writing `~/.claude/scripts/` is outside the sandbox write scope.
