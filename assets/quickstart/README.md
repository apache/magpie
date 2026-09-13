<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [One recording, and a set of authored screenshots](#one-recording-and-a-set-of-authored-screenshots)
  - [Why one is recorded and the rest are written](#why-one-is-recorded-and-the-rest-are-written)
  - [What the check can prove, and what it cannot](#what-the-check-can-prove-and-what-it-cannot)
  - [Adding a screenshot](#adding-a-screenshot)
  - [Conventions](#conventions)
  - [Recording the one recording](#recording-the-one-recording)
  - [Why SVG](#why-svg)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# One recording, and a set of authored screenshots

| File | Embedded by | Shows |
|---|---|---|
| `magpie-setup.svg` | [`docs/quick-start.md`](../../docs/quick-start.md), and [`docs/setup/README.md`](../../docs/setup/README.md) | `/magpie-setup` detecting the checkout, printing its plan, and waiting for approval. A real recording of a real run. |
| `wizard/<family>.svg` | that family's README, *Before the first run* | An **animated** `/magpie-setup config` run for that family. Generated from `requires_config:` frontmatter by [`render-config-wizard.py`](../../tools/dev/render-config-wizard.py) — there is no transcript to edit. Illustrative of the shape of a run, not a recording of one. |
| `families/<family>/<skill>.txt` | — | The authored transcript. This is the source file. |
| `families/<family>/<skill>.svg` | that family's README, *Try these first* | The transcript rendered. Generated; never hand-edited. |

The setup family has no screenshot of `/magpie-setup` itself: its first run
*is* `magpie-setup.svg`, so `docs/setup/README.md` embeds that rather than a
copy.

## Why one is recorded and the rest are written

A capture needs a terminal, a scratch project, and a human — and it needs all
three again the next time any output moves.

That price is worth paying once. `/magpie-setup` is the run a reader has not
done yet, and seeing it actually happen, at the pace it happens, is worth more
than a description of it. So that one is a recording.

It was not worth paying ten times, and the proof is what happened when the
repository tried: nine family recordings sat in the tree as placeholders for
months, and when they were written they all showed the *same* thing — a
pre-flight stopping on an unadopted repo, which is setup's arc, not the
family's. Nine copies of the quick start, filed under ten families.

A screenshot's job on a family page is to show the shape of a run: what comes
back, and how it is laid out. That does not need a capture. It needs someone
to write down what a typical run looks like, which is a text file anyone can
fix in a pull request without booking a recording session.

## What the check can prove, and what it cannot

[`render-screenshot.sh`](../../tools/dev/render-screenshot.sh) is
deterministic: the same `.txt` produces the same `.svg`, byte for byte, on any
machine. So
[`check-quickstart-recording.py`](../../tools/dev/check-quickstart-recording.py)
can prove that **every committed `.svg` still matches its transcript**. Edit
one without re-rendering and the build fails.

It **cannot** prove that a transcript still matches what the skill prints
today. Nothing here can. That is the real cost of authoring rather than
capturing, and it is accepted deliberately: a screenshot on these pages is
there to show the shape of a run, not to serve as a test oracle. Write
transcripts to be robust to cosmetic change and the gap stays small — see the
conventions below.

## Adding a screenshot

```bash
$EDITOR assets/quickstart/families/pairing/self-review.txt
tools/dev/render-screenshot.sh assets/quickstart/families/pairing/self-review.txt
```

Then embed the `.svg` in that family's README under *Try these first*, with
alt text describing what the run shows. `--all` re-renders everything and
`--check` fails on anything stale, which is what runs on commit.

Colour comes from the line itself, so a transcript stays something you read as
a terminal rather than as markup:

| Line | Rendered |
|---|---|
| starts with `> ` | the command, in the prompt colour |
| starts with `✓` | green |
| starts with `⚠` | amber |
| starts with `✗` | red |
| ALL CAPS on its own | a section label, in amber |
| anything else | ordinary output |

## Conventions

- **Under ~20 lines.** A screenshot shows a shape. A reader who wants the
  whole output runs the command.
- **No version strings, no dates, no counts a minor change would move.** The
  check cannot tell you a transcript has gone stale, so write ones that do not
  go stale easily. "reviewed 4 changed files" is fine; "74 skills" is a number
  that will be wrong.
- **Nothing secret in frame** — tokens, private repository names, reporter
  addresses. These files are *text*: anything in them is greppable in the
  repository forever. For `magpie-security` in particular, invent the tracker
  numbers and use a scratch tracker name; a real transcript would put an
  embargoed report in a public repository permanently.
- **Say what the skill does not do.** Most of these skills are read-only or
  draft-then-confirm, and that is the single most reassuring thing a first-time
  reader can see. Several transcripts end on it.
- **Never hand-edit an `.svg`.** It is generated. Edit the `.txt` and
  re-render.
- **Under 1536 KB**, enforced on commit — which an authored screenshot will
  never approach, but the recording could.

## Recording the one recording

[`tools/dev/record-svg.sh`](../../tools/dev/record-svg.sh) does the whole job —
brief, record, convert, prepend the licence header, check the size:

```bash
tools/dev/record-svg.sh setup
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

**Start at `/magpie-setup`.** Adding the marketplace is a one-time
prerequisite with [its own page](../../docs/setup/marketplace-install.md), so
the recording should not open with it — it should open where the reader is.

Keep it short: every redraw of the TUI becomes frames in the SVG, and a
spinner left spinning is pure weight. Thirty seconds is plenty. If a good take
ran long, trim it rather than re-recording — pass `--keep-cast`, then
`tools/dev/record-svg.sh setup --cast <cast> --from 3000 --to 25000`.

## Why SVG

The output is text, which is most of the argument:

- it goes through review as a diff, not as an opaque binary blob;
- it carries its own Apache licence header, so RAT is satisfied by the file
  itself;
- it needs no player and no external host;
- it stays sharp at any width;
- it costs a fraction of what a terminal GIF or a PNG set would add to every
  source release.

The tradeoff for the one animated file: a renderer that does not run SVG
animation shows the first frame rather than the loop. That is an acceptable
still, and GitHub — where these pages are actually read — animates it. The
authored screenshots are static, so they have no such tradeoff.
