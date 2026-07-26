<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the Step 8 mention scan of the pr-management-code-review
skill from the Apache Magpie framework: the last check before a drafted
review is posted to GitHub.

Policy (the skill's mention policy, binding): nothing this skill posts may
live-`@`-mention anyone. Submitting a review already notifies the PR author
and subscribers; a live mention additionally summons the named person
without their consent. Handles are rendered backtick-quoted (`` `@login` ``)
instead, which reads as a handle without notifying. A live mention may
survive only when the maintainer explicitly confirms it with `[K]eep`.

Given a composed review package (review body plus inline comments), scan
everything about to be posted for live `@`-mentions:

- A **live mention** is an `@login` or `@org/team` token in prose —
  outside inline code spans and outside fenced code blocks. GitHub does
  not process mentions inside code spans or fences, so those are NOT live.
- Email addresses (`user@host`) and decorators (`@pytest.fixture`) are not
  mentions.
- For every live mention found, the skill must show the maintainer a
  `[K]eep / [E]scape` prompt before posting. `[E]scape` (rewrite as a
  backtick-quoted handle) is the default; a live mention is never posted
  silently.
- If no live mention is found, no prompt is shown and posting proceeds.

## Output

Return ONLY valid JSON with this structure:
{
  "live_handles": ["<login>", ...],
  "prompt_shown": true | false,
  "reason": "<one sentence naming what was found and what happens next>"
}

`live_handles` lists the bare logins (no `@`) of every live mention found,
sorted alphabetically, empty when none. `prompt_shown` is true only when
`live_handles` is non-empty. Do not include any text outside the JSON
object.
