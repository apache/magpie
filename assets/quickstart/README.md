<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [The quick-start recordings](#the-quick-start-recordings)
  - [What these replaced, and why](#what-these-replaced-and-why)
  - [Recording them](#recording-them)
    - [What a family take must contain](#what-a-family-take-must-contain)
  - [Conventions](#conventions)
  - [Why SVG](#why-svg)
  - [The placeholders](#the-placeholders)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# The quick-start recordings

This directory holds ten animated SVGs — one per page that needs to show
Magpie running:

| Recording | Embedded by | Shows |
|---|---|---|
| `magpie-setup.svg` | [`docs/quick-start.md`](../../docs/quick-start.md) Step 2, and [`docs/setup/README.md`](../../docs/setup/README.md) | The marketplace install, then `/magpie-setup` detecting the checkout, printing its plan, and waiting for approval. |
| `families/<family>-first-run.svg` × 9 | that family's README, *Install & first runs* | That family's **first** run: the pre-flight finding no project config, stopping to propose `/magpie-setup`, and the same command succeeding on the retry. |

The setup family has no first-run recording of its own. Its first run *is*
`magpie-setup.svg`, so `docs/setup/README.md` embeds that rather than a copy.

## What these replaced, and why

Fourteen still screenshots — four harness install shots and ten per-family
ones, with a design on file to grow them to twenty-five. Every one of them
showed the same thing, a `/plugin` list with a plugin in it. They proved an
install had succeeded and nothing else, they went stale the moment the plugin
UI moved, and keeping them consistent meant a fourteen-window capture session
nobody wanted to repeat.

The first run is the part worth showing. 65 of the 74 skills open with a
silent pre-flight that stops and proposes `/magpie-setup` when the project is
not adopted — a reader who has seen that happen once knows what to expect, and
a still frame cannot show it.

## Recording them

[`tools/dev/record-svg.sh`](../../tools/dev/record-svg.sh) does the whole job —
brief, record, convert, prepend the licence header, check the size:

```bash
tools/dev/record-svg.sh --list       # every target
tools/dev/record-svg.sh setup        # the quick-start recording
tools/dev/record-svg.sh security     # one family's first run
```

It needs two things:

```bash
brew install asciinema     # or: pipx install asciinema
# svg-term-cli is fetched on demand via npx — Node is the only other requirement
```

asciinema 2 and 3 both work. asciinema 3 records the newer asciicast **v3**,
which `svg-term-cli` cannot open — it reads v1 and v2 only — so the script
converts the take to v2 first, and pins the 145x35 frame with whichever size
flag the installed asciinema takes (`--window-size`, or the older
`--cols`/`--rows`). Getting that second one wrong is silent: asciinema 3
accepts `--cols`/`--rows` and ignores them.

Record **in a scratch project, from your own terminal.** Not in a Magpie
checkout: this repo commits the auto-install block and is already adopted, so
there is no pre-flight failure to show and the install step records as a no-op.

### What a family take must contain

The arc, in order — this is the whole point of the recording:

1. the skill starting, and its pre-flight finding no `<project-config>`;
2. it **stopping** and proposing `/magpie-setup` rather than guessing;
3. setup running;
4. the same command again, now working.

A take that skips to a working run shows the one thing a reader can already
assume. The command to use is the first one from that family's README under
*Try these first*.

## Conventions

- **Keep it short.** This is the one that bites. Every redraw of the TUI
  becomes frames in the SVG, and a spinner left spinning is pure weight.
  Thirty seconds is plenty; a couple of minutes will blow the size cap.
  If a good take ran long, trim it rather than re-recording — pass
  `--keep-cast`, then
  `tools/dev/record-svg.sh <target> --cast <cast> --from 3000 --to 25000`.
- **Under 1536 KB**, enforced on commit. The script warns at 1024 KB.
- **Dark theme**, consistent across all ten.
- **Nothing secret in frame** — tokens, private repo names, reporter
  addresses, the window title, the status line. These files are *text*:
  anything on screen is greppable in the repository forever. For
  `magpie-security` in particular, point the recording at a scratch tracker,
  never a real one — a real take would put an embargoed report in a public
  repository permanently.
- **Never hand-edit an SVG.** They are generated. Re-record or retrim instead.

## Why SVG

The output is text, which is most of the argument:

- it goes through review as a diff, not as an opaque binary blob;
- it carries its own Apache licence header, so RAT is satisfied by the file
  itself;
- it loops natively in a GitHub README with no player and no external host;
- it stays sharp at any width;
- it costs a fraction of what a terminal GIF would add to every source
  release — the cap here is 1.5 MB against the 3–6 MB a GIF of the same take
  would weigh, and there are ten of them.

The tradeoff: a renderer that does not run SVG animation shows the first frame
rather than the loop. That is an acceptable still, and GitHub — where these
pages are actually read — animates them.

## The placeholders

All ten currently ship as **placeholders** reading "recording pending", not
real captures. They exist so the pages render and the offline link check
passes before the recordings are made.
[`tools/dev/check-quickstart-recording.py`](../../tools/dev/check-quickstart-recording.py)
recognises them by their `data-magpie-placeholder` marker and reports how many
remain on every run. Replace each at the same path; no documentation change is
needed, the alt text already describes what each recording shows.
