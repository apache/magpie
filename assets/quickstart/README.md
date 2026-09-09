<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Quick-start screenshots — capture checklist](#quick-start-screenshots--capture-checklist)
  - [Per-family install shots — `families/`](#per-family-install-shots--families)
  - [The capture helper](#the-capture-helper)
  - [Capture conventions](#capture-conventions)
  - [Regenerating the placeholders](#regenerating-the-placeholders)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Quick-start screenshots — capture checklist

The four screenshots in this directory are referenced by
[`docs/quick-start.md`](../../docs/quick-start.md). They currently ship as
**generated placeholders**, not real captures — the page renders and the link
check passes, but the images say so on their face.

To finish the page, capture each shot below and overwrite the file **at the
same path and name**. No documentation change is needed; the alt text in
`quick-start.md` already describes what each shot must show.

| File | Agent | Capture this |
|---|---|---|
| `claude-code-install.png` | Claude Code | Run `/plugin marketplace add apache/magpie`, then `/plugin install magpie-setup@apache-magpie` and `/plugin install magpie-pr-management@apache-magpie`, then `/plugin`. Frame the plugin list with **both family plugins** installed and enabled — per-family is the recommended install, so don't capture the all-in-one `magpie` plugin here. |
| `codex-install.png` | OpenAI Codex CLI | Run `codex plugin marketplace add apache/magpie` and `codex plugin install magpie`, then `/plugins` inside Codex (or `codex plugin list`). Frame the output listing **magpie**. |
| `vscode-install.png` | VS Code / GitHub Copilot | Install from the repo URL `https://github.com/apache/magpie`. Frame the VS Code plugin view showing **Apache Magpie** installed. |
| `gemini-install.png` | Google Gemini CLI | Run `gemini extensions install https://github.com/apache/magpie`, then `gemini extensions list`. Frame the terminal output showing the **magpie** extension. |

## Per-family install shots — `families/`

Each family README carries an **Install & first runs** section with one
screenshot: `families/<family>-install.png`. Same treatment as above — they
ship as placeholders until captured.

Ten files, one per family: `setup`, `utilities`, `security`, `pr-management`,
`issue`, `release-management`, `repo-health`, `pairing`, `mentoring`,
`contributor-growth`.

Capture each the same way, in Claude Code:

```text
/plugin marketplace add apache/magpie
/plugin install magpie-<family>@apache-magpie
/plugin
```

Frame the plugin list showing **that one family plugin** installed and enabled.
One family per shot — the point of the section is that you install only what
you need, so a screenshot showing six plugins undercuts the page it sits on.

The usage examples in those sections are deliberately **text blocks, not
screenshots**: they are illustrative shapes rather than real transcripts, and
they are labelled as such in each README. Do not replace them with real
captures without checking that no private tracker content, reporter address,
or embargoed security detail is in frame.

## The capture helper

`tools/dev/capture-screenshot.sh` does the whole job for one shot — brief,
capture, resize, strip metadata, write to the right path:

```bash
tools/dev/capture-screenshot.sh security      # a family shot
tools/dev/capture-screenshot.sh claude-code   # a harness shot
tools/dev/capture-screenshot.sh --list        # every valid target
```

It applies the conventions below for you. macOS only, and run it from your own
terminal: Screen Recording permission is granted per calling application, so
calling it from inside an agent's shell tends to fail silently.

## Capture conventions

- **Crop tight.** Show the command and its result — not the whole desktop, not
  an empty scrollback. The reader is checking "did it work", nothing more.
- **Dark or light is fine**, but keep all four consistent within a set.
- **No secrets in frame** — no tokens, no private repo names, no email
  addresses in a prompt or status line. Check the terminal title bar too.
- **~1400px wide** is enough; the existing `assets/session-*.png` captures are
  a good size reference.
- **PNG**, and keep each file well under 500 KB.

## Regenerating the placeholders

The placeholders are produced by ImageMagick, one command per file, e.g.:

```bash
magick -size 1200x300 canvas:'#1d1f21' \
  -fill '#c5c8c6' -pointsize 30 -gravity center \
  -annotate 0 'screenshot pending\nclaude-code-install.png\nsee assets/quickstart/README.md' \
  assets/quickstart/claude-code-install.png
```
