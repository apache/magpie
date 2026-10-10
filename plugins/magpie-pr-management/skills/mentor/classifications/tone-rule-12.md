<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 12 — Comment is short

**Severity:** soft fail — revise once before showing the maintainer. **Checked by:** `mentor tone-check` detects it.

Soft cap at 6 sentences (excluding the footer). Beyond that, the comment is doing too much — likely violating rule 6.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
