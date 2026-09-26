<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Link form — clickable issue, PR, and comment references

Companion to [`SKILL.md`](SKILL.md). Body of Golden rule 5: the clickable
reference forms for issue, PR, and comment links on markdown and terminal
surfaces, plus the self-check run before posting any proposal.

Whenever this skill emits a reference
to an issue, PR, or comment — the proposal body, the action-items
list, the recap output — the reference must be one click away in
whatever surface it lands on:

- **On markdown surfaces** (the proposal comment posted to
  `<issue-tracker>`, any markdown-rendered action-items block): use
  the markdown link form per
  [`AGENTS.md` § *Linking tracker issues and PRs*](../../../../AGENTS.md#linking-tracker-issues-and-prs):
  - **Issue**: `[<issue-tracker>#NNN](https://github.com/<issue-tracker>/issues/NNN)`
  - **PR**: `[<upstream>#NNN](https://github.com/<upstream>/pull/NNN)`
  - **Comment**: link to the `#issuecomment-<C>` anchor.

- **On terminal surfaces** (the pre-post proposal preview, the
  recap printed at the end): wrap the visible short form in
  **OSC 8 hyperlink escape sequences**
  (`\e]8;;<URL>\e\\<short>\e]8;;\e\\`) so modern terminals
  (iTerm2, Kitty, GNOME Terminal, WezTerm, Windows Terminal, …)
  render the short text as clickable. Where OSC 8 is unsupported
  (CI logs, dumb terminals), fall back to printing the bare URL
  on the same line after the number.

Bare `issue:NNN` / `#NNN` with no link wrapper of any kind is
never acceptable.

**Self-check before posting any proposal**: grep the body for
bare `#\d+` / `issue:\d+` tokens that aren't already inside a
markdown link or an OSC 8 wrapper, and convert any match.
