<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code. Framework checkout, but a shallow clone: `git rev-parse --is-shallow-repository` prints `true`. Personal layer: `.apache-magpie-local/`. Isolated setup: configured.

Findings:
- slug: overlay-script-differs. `~/.claude/scripts/gpg-touch-overlay.sh` differs from `tools/agent-isolation/gpg-touch-overlay.sh`.
  The diff shows 2 lines present in the user-scope copy that the framework copy lacks, and 3 lines the framework copy has that the user-scope copy lacks; the framework copy fixes a security problem.
  Gather looked the copy's blob hash up in the git log of that file and found no match, but the log covers only the shallow history.
  Writing `~/.claude/scripts/` is outside the sandbox write scope.
