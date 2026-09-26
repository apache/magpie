<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Clickable references — link contract for emitted mentions

Companion to [`SKILL.md`](SKILL.md). The body of Golden rule 8:
the link form required per surface, and the self-check before
writing a verdict.json or printing a session summary.

Whenever this skill
emits a reference to an issue, PR, or commit — the per-issue
verdict.json (`url` / `linked_prs` fields), the session summary,
the recap output, the headline lists shown to the user — the
reference must be one click away in whatever surface it lands on:

- **On data / markdown surfaces** (verdict.json `url` fields
  consumed downstream as raw URLs; any tracker comment posted on
  `<issue-tracker>`; markdown-rendered headline tables): use the
  full URL (verdict.json) or the markdown link form per
  [`AGENTS.md` § *Linking tracker issues and PRs*](../../../../AGENTS.md#linking-tracker-issues-and-prs):
  - **Issue**: `[<issue-tracker>#NNN](https://github.com/<issue-tracker>/issues/NNN)`
  - **PR**: `[<upstream>#NNN](https://github.com/<upstream>/pull/NNN)`
  - **Commit**: `[<sha>](https://github.com/<upstream>/commit/<sha>)`

- **On terminal surfaces** (the session summary printed at the
  end of a campaign, progress lines shown during the sweep,
  recap output): wrap the visible short form
  (`<issue-tracker>#NNN`, `<upstream>#NNN`) in **OSC 8 hyperlink
  escape sequences** (`\e]8;;<URL>\e\\<short>\e]8;;\e\\`) so
  modern terminals (iTerm2, Kitty, GNOME Terminal, WezTerm,
  Windows Terminal, …) render the short text as clickable. Where
  OSC 8 is unsupported (CI logs, dumb terminals), fall back to
  printing the bare URL on the same line after the number.

Bare `#NNN` with no link wrapper of any kind is never acceptable
— the verdict.json artefact is consumed downstream by
`issue-reassess-stats` as drill-down evidence, and unclickable
references force the user to manually reconstruct URLs.

**Self-check before writing a verdict.json file or printing a
session summary**: grep the body for bare `#\d+` tokens that
aren't already inside a markdown link, a raw `https://...` URL,
or an OSC 8 wrapper, and convert any match.
