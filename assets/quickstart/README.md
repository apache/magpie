<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Quick-start screenshots — capture checklist](#quick-start-screenshots--capture-checklist)
  - [Per-family install shots — `families/`](#per-family-install-shots--families)
  - [The capture helper](#the-capture-helper)
  - [The auto-install shot — `claude-code-default-install.png` *(optional)*](#the-auto-install-shot--claude-code-default-installpng-optional)
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

> [!IMPORTANT]
> **Capture these outside a Magpie-adopting project.** Since the default set
> landed, a project that commits the
> [auto-install block](../../docs/setup/marketplaces.md#claude-code-the-default-set)
> — this repository included — opens with `magpie-setup`, `magpie-utilities`
> and `magpie-agent-guard` already enabled, so `/plugin` shows *four* entries
> where the shot needs one. Use a scratch project with no such block, and clear
> the `magpie-*` entries from your own user-scope `enabledPlugins` first. The
> same applies to `claude-code-install.png`. The capture helper prints this
> reminder for every Claude Code target.

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

You click the window you want and it captures that window whole, so the crop is
identical across a set. It applies the conventions below for you. macOS only,
and run it from your own terminal: Screen Recording permission is granted per calling application, so
calling it from inside an agent's shell tends to fail silently.

## The auto-install shot — `claude-code-default-install.png` *(optional)*

[`docs/setup/marketplaces.md`](../../docs/setup/marketplaces.md#auto-install-arriving-magpie-ready)
describes a project that commits `enabledPlugins`, so a contributor who clones
it finds the **default set** already installed: `magpie-setup`,
`magpie-utilities`, and the `magpie-agent-guard` substrate plugin. This shot is
**optional** — unlike the others it has to be *staged*, not merely captured,
and the capture helper has no target for it.

What makes it hard: the shot has to prove you installed nothing. Taken on your
own machine it proves the opposite, because your user-scope `enabledPlugins`
already has Magpie in it.

1. Temporarily remove the `magpie-*` entries from your **user-scope**
   `~/.claude/settings.json` `enabledPlugins` — keep a copy to restore.
2. Open Claude Code in a project whose committed `.claude/settings.json` has
   the `extraKnownMarketplaces` + `enabledPlugins` block, and accept the trust
   prompt.
3. Run `/plugin` and frame the list showing **all three default plugins
   installed and enabled, and every opt-in family absent**. The absence is the
   whole point — a shot that also shows `magpie-security` demonstrates nothing
   the manual-install shots do not. Include `magpie-agent-guard`: it is the
   least obvious member of the set and the one a reader is most likely to
   assume they have to install by hand.
4. Restore your own settings.

Same conventions as every other shot; `check-quickstart-screenshots.py` holds
it to them if it exists, and ignores it if it does not.

## Capture conventions

- **Size the window tight.** The capture is the window, so the window *is* the
  crop: shrink it to the command and its result — no empty scrollback below.
  The reader is checking "did it work", nothing more.
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
