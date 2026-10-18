<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 10 — No predictions about review outcome

**Severity:** hard fail — the comment cannot be posted. **Checked by:** `mentor tone-check` detects it.

Reject if the draft contains "looks good", "this should be approved", "this will probably be merged", "I don't think this will land". Agentic Mentoring does not signal review outcomes.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
