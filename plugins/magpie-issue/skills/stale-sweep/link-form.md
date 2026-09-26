<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Link form — clickable issue references

Companion to [`SKILL.md`](SKILL.md). Per-surface link forms for issue
references (Golden rule 5) and the bare-`#NNN` self-check.

Whenever this skill emits a reference to an issue — the proposal body,
the confirmation screen, the recap — it must be one click away in
whatever surface it lands on:

- **On markdown surfaces** (comment body posted to `<issue-tracker>`,
  confirmation-screen preview): use the markdown link form per
  [`AGENTS.md` § *Linking tracker issues and PRs*](../../../../AGENTS.md#linking-tracker-issues-and-prs):
  `[<issue-tracker>#NNN](https://github.com/<issue-tracker>/issues/NNN)`.

- **On terminal surfaces** (the pre-post preview, the recap): wrap the
  visible short form in **OSC 8 hyperlink escape sequences**
  (`\e]8;;<URL>\e\\<short>\e]8;;\e\\`). Fall back to printing the bare
  URL on the same line after the number when OSC 8 is unsupported.

Bare `#NNN` with no link wrapper of any kind is never acceptable.

**Self-check before posting any comment**: grep the body for bare `#\d+`
tokens that aren't already inside a markdown link or an OSC 8 wrapper,
and convert any match.
