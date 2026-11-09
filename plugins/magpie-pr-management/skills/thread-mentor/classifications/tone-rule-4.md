<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 4 — No speaking for the maintainer

**Severity:** hard fail — the comment cannot be posted. **Checked by:** `mentor tone-check` detects it.

Reject if the draft contains "the maintainers will probably", "the maintainers want", "the team would prefer", or any forward-looking claim about a maintainer decision. The skill says "a maintainer will reply" and stops.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
