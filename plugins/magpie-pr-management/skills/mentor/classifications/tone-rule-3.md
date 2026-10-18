<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 3 — No AI self-reference outside the footer

**Severity:** hard fail — the comment cannot be posted. **Checked by:** `mentor tone-check` detects it.

Reject if the body (everything before `<ai_attribution_footer>`) contains "as an AI", "I'm an AI", "I cannot", "as a language model", "I was trained", "my training", or "I don't have access to". The footer says it once. The body says nothing.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
