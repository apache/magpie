<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 8 — Author tagged once

**Severity:** hard fail — the comment cannot be posted. **Checked by:** `mentor tone-check` detects it.

Reject if `@<author>` appears zero times or more than once. The first line tags; the rest of the comment does not.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
