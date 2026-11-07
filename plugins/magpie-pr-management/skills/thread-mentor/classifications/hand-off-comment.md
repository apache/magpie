<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The hand-off comment

One template for all four triggers. It does **not** summarise the conversation — the maintainer reads the thread.

1. Write one short sentence naming what is unresolved to `<scratch>/open-question.txt`. It must reference the thread, not interpret it.
2. Render:

   ```bash
   uv run --project <framework>/tools/pr-management pr-management mentor render --kind hand-off --open-question-file <scratch>/open-question.txt --out <scratch>/handoff.md
   ```

   The renderer tags `maintainer_team_handle`, links bare `#NNN`, and backtick-quotes any other handle.
3. Show the maintainer the preview and wait for explicit confirmation. Never auto-post a hand-off — a mis-rendered one pings a whole team.
4. On confirmation, post it:

   ```bash
   gh issue comment <N> --repo <upstream> --body-file <scratch>/handoff.md
   ```

   (`gh pr comment` for a PR.) The agent-guard `mention` guard lets this one team mention through: the team is the `maintainer_team_handle` in `.apache-magpie-overrides/mentoring-config.md` as GitHub serves it from the target repository's default branch (a local edit does not count), it belongs to the organisation that owns that repository, and the body opens with the template's `— handing this off:` line. Any other mention in the body is still blocked.
5. Record it: `uv run --project <framework>/tools/pr-management pr-management mentor log --kind <pr|issue> --number <N> --outcome handed-off --trigger <n>`. The skill does not return to a handed-off thread.

The hand-off never contains a summary of the thread, a guess at what the maintainer should do, an apology, a retry offer, or a further doc link: anything added pre-loads the maintainer's read of the conversation.
