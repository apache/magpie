<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Clickable references

Companion to [`SKILL.md`](SKILL.md). Full body of Golden rule 8 — emitting issue, PR, and commit references so they are clickable in every surface.

Whenever
this skill emits a reference to an issue, PR, or commit — the
hand-back artefact printed to the user's terminal, the proposed
commit message body, the draft PR body the human committer will
use, any tracker comment posted on `<issue-tracker>` — the
reference must be one click away in whatever surface it lands on:

- **On markdown surfaces** (the draft PR body, the commit-message
  body destined for `git log`, any tracker comment posted on
  `<issue-tracker>`): use the markdown link form per
  [`AGENTS.md` § *Linking tracker issues and PRs*](../../../../AGENTS.md#linking-tracker-issues-and-prs):
  - **Issue**: `[<issue-tracker>#NNN](https://github.com/<issue-tracker>/issues/NNN)`
  - **PR**: `[<upstream>#NNN](https://github.com/<upstream>/pull/NNN)`
  - **Commit**: `[<sha>](https://github.com/<upstream>/commit/<sha>)`

- **On terminal surfaces** (the hand-back artefact, the targeted
  test-run output the user reads): wrap the visible short form
  (`<issue-tracker>#NNN`, `<upstream>#NNN`, or first-7-of-`<sha>`)
  in **OSC 8 hyperlink escape sequences**
  (`\e]8;;<URL>\e\\<short>\e]8;;\e\\`) so modern terminals
  (iTerm2, Kitty, GNOME Terminal, WezTerm, Windows Terminal, …)
  render the short text as clickable. Where OSC 8 is unsupported
  (CI logs, dumb terminals, plain captures), fall back to
  printing the bare URL on the same line after the number.

Bare `#NNN` with no link wrapper of any kind is never acceptable
— not in the hand-back, not in the draft PR body, not in the
commit message.

**Self-check before emitting any text**: grep for bare `#\d+`
tokens that aren't already inside a markdown link or an OSC 8
wrapper, and convert any match. If the reference is to an issue
or PR the skill doesn't have the full URL for yet, look it up
before emitting (`gh issue view <N> --json url` or
`gh pr view <N> --json url`).
