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
  - [The animated runs](#the-animated-runs)
  - [Why SVG](#why-svg)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# One recording, and a set of authored screenshots

| File | Embedded by | Shows |
|---|---|---|
| `magpie-setup.svg` | [`docs/quick-start.md`](../../docs/quick-start.md), and [`docs/setup/README.md`](../../docs/setup/README.md) | `/magpie-setup` detecting the checkout, printing its plan, and waiting for approval. A real recording of a real run. |
| `wizard/<family>.svg` | that family's README, *Before the first run* | An **animated** `/magpie-setup config` run for that family. Generated from `requires_config:` frontmatter by [`render-wizard.py`](../../tools/dev/render-wizard.py) — there is no transcript to edit. Illustrative of the shape of a run, not a recording of one. |
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
- **Under 1536 KB**, enforced on commit. Nothing generated here comes close;
  the cap catches a transcript that grew without anyone noticing.

## The animated runs

[`tools/dev/render-wizard.py`](../../tools/dev/render-wizard.py) writes them
all:

```bash
python3 tools/dev/render-wizard.py           # write
python3 tools/dev/render-wizard.py --check   # fail on drift
```

`magpie-setup.svg` is one fixed arc — the agent detected, the families picked,
the install commands, then the secure-agent setup applying the sandbox, the
clean-environment wrapper, the hooks and the status line. Edit
`setup_script()` to change it. The per-family runs under `wizard/` have no
script to edit: they are derived from each family's skills' `requires_config:`
frontmatter, so a family that gains a required file gains a frame by itself.

Animation is SMIL — one `<animate>` on opacity per line, all sharing one
duration so the sequence loops as a unit. A viewer that does not animate SVG
shows the first frame, which is the command about to be typed.

**Nothing in this repository is captured.** `magpie-setup.svg` was the last
recording, made with `asciinema` and `svg-term-cli`. It was also wrong: it
opened with the marketplace install, which became a prerequisite with its own
page, and fixing that needed a terminal, a scratch project and a human — which
is why it stayed wrong for as long as it did. The recorder is retired and the
Node dependency with it.

What that costs is the same thing the authored screenshots cost, and it is
worth restating here: a generated animation cannot prove the program still
behaves the way the picture says. It shows the *shape* of a run — what is
asked, in what order, and what is written where — and every embed says so.

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
