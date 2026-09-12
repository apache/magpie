<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Example-command recordings](#example-command-recordings)
  - [What exists](#what-exists)
  - [Recording one](#recording-one)
  - [Before adding a family](#before-adding-a-family)
  - [Conventions](#conventions)
  - [The placeholders](#the-placeholders)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Example-command recordings

Animated SVGs of **one command doing one thing**, embedded by a family
README's *Try these first* section. One file per command, named after the
command it records: `<family>-<skill>.svg` for `/magpie-<family>:<skill>`.

These are a different job from the recordings in
[`assets/quickstart/`](../quickstart/README.md). Those show *setup* — the
quick start's `/magpie-setup` run, and each family's first run stopping at the
pre-flight. These show a skill's **output**: what you get back when you run it
on a project that is already set up.

## What exists

| Recording | Command | Embedded by |
|---|---|---|
| `pairing-self-review.svg` | `/magpie-pairing:self-review` | [`docs/pairing/README.md`](../../docs/pairing/README.md) |
| `pairing-multi-agent-review.svg` | `/magpie-pairing:multi-agent-review` | [`docs/pairing/README.md`](../../docs/pairing/README.md) |

**`magpie-pairing` went first for a reason.** Both its skills are read-only
and act on *your own local diff* — there is no tracker, no mailbox, no
reporter, and nothing that leaves the machine. A recording of either can be
made against a throwaway change with nothing sensitive anywhere near it.

That is not true of every family, which is why this directory holds two files
rather than thirty. See [Before adding a family](#before-adding-a-family).

## Recording one

```bash
tools/dev/record-svg.sh pairing:self-review
```

The target is spelled exactly like the slash command. Any skill a family
plugin ships is a valid target; the checker expects a file to exist only once
a README embeds it, and fails on one no README references.

Record on a project that is **already set up** — an example is not a first-run
recording, so there should be no pre-flight failure and no `/magpie-setup` in
frame. Show the command and its result, and stop.

Frame a result a reader can learn the shape of: the summary line and the
findings, not a wall of scrollback.

## Before adding a family

These files are **text**. Anything on screen is greppable in the repository
forever, and unlike a screenshot there is no pixel-scraping step between a
reader and the content. Before recording a family that touches real data, work
out what would end up in the file:

- **`magpie-security` — do not record against a real tracker.** A take of
  `issue-triage` or `issue-sync` puts an embargoed report, a reporter's
  address, or an unpublished CVE into a public repository permanently. If it
  is recorded at all, it must be against a scratch tracker seeded with
  invented reports.
- **`magpie-issue` and `magpie-pr-management`** surface real issue and PR
  content. Public, but still someone's words — use a scratch repo.
- **`magpie-contributor-growth` and `magpie-mentoring`** put named people in
  frame. Use invented handles.

The families' *Try these first* blocks are labelled as illustrative shapes
rather than real transcripts precisely because this was never resolved for
them. Replacing a block with a recording means resolving it first.

## Conventions

Same as the quick-start recordings — see
[that recipe](../quickstart/README.md#conventions) for the full list:

- **keep it short**; every TUI redraw is frames in the file;
- **under 1536 KB**, enforced on commit, with a warning at 1024 KB;
- **dark theme**, consistent with every other recording;
- **nothing secret in frame**, per the section above;
- **never hand-edit** — they are generated; re-record or retrim.

## The placeholders

Both currently ship as **placeholders** reading "recording pending". They
exist so the page renders and the offline link check passes before the
recordings are made.
[`tools/dev/check-quickstart-recording.py`](../../tools/dev/check-quickstart-recording.py)
recognises them by their `data-magpie-placeholder` marker and reports how many
remain. Replace each at the same path; no documentation change is needed, the
alt text already describes what each recording shows.
