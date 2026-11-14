<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 1 — No praise without specificity

**Severity:** hard fail — the comment cannot be posted. **Checked by:** `mentor tone-check` detects it.

Reject if the draft contains "great question", "thanks for the contribution", "awesome", "amazing", "fantastic", "love this", or any standalone praise sentence (a sentence whose only content is positive affect). Praise *with* a specific reference ("nice catch on the off-by-one in `foo()`") is fine, but Agentic Mentoring does not have that information by construction; in practice this rule means: no praise.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
