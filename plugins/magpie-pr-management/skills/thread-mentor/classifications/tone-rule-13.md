<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tone rule 13 — Plain English

**Severity:** soft fail — revise once before showing the maintainer. **Checked by:** your judgement — the checker cannot see it.

Reject jargon the contributor is unlikely to know without the link being clicked. If the draft uses a project-internal term, it should appear inside the linked label, not in prose.

Revise the draft and run `uv run --project <framework>/tools/pr-management pr-management mentor tone-check --draft <draft> --author <author>` again.
If a second revision still fails a hard rule, show the maintainer the rule and the offending sentence and ask for guidance — never post a comment that fails tone.
