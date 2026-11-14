<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 2 — No restating the contributor's message

**Severity:** hard fail — the comment cannot be posted. **Checked by:** `mentor tone-check` catches the listed phrases; the rest is your judgement.

Reject if the draft contains "so what you're saying is", "if I understand correctly", "you mentioned that", or any sentence whose content is a paraphrase of the contributor's most recent message.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
