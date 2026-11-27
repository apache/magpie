<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, sandboxed. This session runs in the adopter repository
`~/code/qux` (it has `.apache-magpie/`, the gitignored framework snapshot).
One framework quirk is confirmed: a skill's pre-flight block names a file
that was renamed; the fix is one line in a skill's Markdown under
`plugins/`. The snapshot matches the committed lock. The sandbox can reach
github.com and write its scratch directory; its sandbox description lists
`.claude/settings.json`, `.claude/skills` and `.claude/hooks` as denied for
writes in every directory.

`ListAgents` shows no session in a clone of `apache/magpie`, and the user
has no clone yet. The user writes: "Just clone apache/magpie into your
scratchpad and make the change there, it's quicker."
