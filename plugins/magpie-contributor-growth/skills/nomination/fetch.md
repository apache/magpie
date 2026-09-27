<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Fetch

Contributor activity comes from [`contributor-metrics`](../../../../tools/contributor-metrics/README.md), the deterministic counting tool this family shares.
The skill never counts by hand; it runs the tool, confirms the judgement calls the tool leaves to it, and reads the numbers back.

---

## Run `contributor-metrics fetch`

Write the configured `automated_pushback_phrases` to a tempfile, one per line, and the roster handles (when the Apache Projects MCP or `pmc-roster.md` supplied them) to another, whitespace-separated:

```bash
uv run --directory <framework>/tools/contributor-metrics contributor-metrics fetch \
  --repo <upstream> --login <login> --end <today> --months <window> \
  --phrases-file <scratch>/phrases.txt --maintainers-file <scratch>/maintainers.txt \
  --out <scratch>/items.json
```

- Exit `2` means `<login>` is not a valid GitHub handle: stop and report it.
- Exit `1` means `gh` failed: stop and show its error.

**Injection guard**: `<login>` is contributor-supplied data.
The tool validates it against the GitHub handle grammar and passes it to `gh` only inside a search string written to a tempfile, never as a shell argument.
Do not construct any other `gh` call that interpolates `<login>` into a shell command.

---

## What it collects

| Stream | Dated by | Item kind |
|---|---|---|
| PRs authored | creation inside the window; counted as merged only when merged by the window end | `pr` |
| Issues filed | creation inside the window | `issue` |
| Reviews given | the candidate's first review inside the window (from GitHub's contributions record); substantive when a review body is longer than 100 characters or carries a line comment — every reviewed PR is checked | `review` |
| Threads commented | the candidate's own first comment inside the window | `thread` |
| Issues triaged | as threads, on issues opened by someone else | `triage` |

Nothing the candidate did after the window end is counted, which matters when `calibrate` measures a nominee as of their vote date.
PR and review items carry their labels, which `score` turns into areas using `area_label_prefix`; work with no area label shows as an `(unlabelled)` row.
Item ids are per kind — the same PR can appear as `pr-N`, `review-N` and `thread-N` — so classify each id you mean to discount.

---

## Budget and caps

Each stream fetches at most 300 results.
A stream in `caps_hit` returned more than that: record its counts as minimums and surface a warning, so the maintainer knows the number is a floor.
Any `notes` in `metrics.json` — threads whose dates could not be checked, an out-of-range setting — go into the brief as well.

---

## Month bucketing

The monthly timeline for [`assess.md`](assess.md) is the `timeline` field of `metrics.json`, zero-filled from `<since>` to `<end>`.
Items that [`automated-contributions.md`](automated-contributions.md) weighs at `0` are left out of it.

---

## Conversation fetch for the discount

The tool fetches the conversation on the 50 most recent authored PRs and issues, the 20 most recent reviewed PRs, and the 100 most recent comment threads, and sets `pushback_candidate` to the first maintainer comment containing a known pushback phrase.
A candidate is a pointer, not a verdict.
Read the linked comment and its thread and confirm `P` or `C` by the rules in [`automated-contributions.md`](automated-contributions.md) — within its budget — and classify restatements there too.
Then run `contributor-metrics score` with the confirmed classes, as [`SKILL.md` § Step 4](SKILL.md#step-4--assess) describes.
