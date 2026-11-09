<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 5 — No hedging

**Severity:** hard fail — the comment cannot be posted. **Checked by:** `mentor tone-check` detects it.

Reject if the draft contains "it seems like", "perhaps", "I think maybe", "this might possibly", "I'm not sure but". The pointer is either right or shouldn't be posted.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
