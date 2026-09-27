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

| Stream | Search | Item kind |
|---|---|---|
| PRs authored | `repo:<upstream> type:pr author:<login> created:<since>..<end>` | `pr` |
| Issues filed | `repo:<upstream> type:issue author:<login> created:<since>..<end>` | `issue` |
| Reviews given | `repo:<upstream> type:pr reviewed-by:<login> updated:>=<since>` | `review` |
| Threads commented | `repo:<upstream> commenter:<login> updated:>=<since>` | `thread` |
| Issues triaged | `repo:<upstream> type:issue commenter:<login> -author:<login> updated:>=<since>` | `triage` |

A review is **substantive** when its body is longer than 100 characters or it carries a line comment; the ten most recent reviewed PRs get that depth check.
PR and review items carry their labels, which `score` turns into areas using `area_label_prefix`.

---

## Budget and caps

Each stream fetches at most 300 results.
A stream in `caps_hit` returned more than that: record its counts as minimums and surface a warning, so the maintainer knows the number is a floor.

---

## Month bucketing

The monthly timeline for [`assess.md`](assess.md) is the `timeline` field of `metrics.json`, zero-filled from `<since>` to `<end>`.
Items that [`automated-contributions.md`](automated-contributions.md) weighs at `0` are left out of it.

---

## Conversation fetch for the discount

The tool fetches the conversation on the 50 most recent authored PRs and issues and the 50 most recent comment threads, and sets `pushback_candidate` to the first maintainer comment containing a known pushback phrase.
A candidate is a pointer, not a verdict.
Read the linked comment and its thread and confirm `P` or `C` by the rules in [`automated-contributions.md`](automated-contributions.md) — within its budget — and classify restatements there too.
Then run `contributor-metrics score` with the confirmed classes, as [`SKILL.md` § Step 4](SKILL.md#step-4--assess) describes.
