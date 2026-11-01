<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The `[DISCUSS]` email

How Step 6 turns the briefs into the email that opens the nomination discussion on `<private-list>`.
The email is a draft in the nominator's voice: the agent never sends it, and creates a mail draft only on an explicit yes.

---

## One thread for everyone

By default every candidate goes into **one** `[DISCUSS]` thread, however many there are and whatever their targets.
Open one thread per candidate only when the nominator asks for it (`discuss:per-candidate`, or *"separate threads"*); the layout of each is then the single-candidate form below.
The `[VOTE]` threads that follow the discussion stay one per candidate, as the closing line of the email says.

---

## How much detail to share

Ask once, before drafting, unless `details:` was given: *"How much should the email show about each candidate's work?"*

| Level | Each candidate's block holds |
|---|---|
| `names` | Name, handle, target, and the personal note. No counts, no links. |
| `summary` | Plus a short factual summary of their work in your own words, with the headline adjusted counts. No links. |
| `links` (default) | Plus two or three links to representative landed changes, one per line. |
| `full` | Plus the **Details** links to the live code-host searches of their activity in the window (per [`candidate-screen` → Details links](../candidate-screen/report.md#details-links)), and the factual flags from the brief: pushback on automated work, one area or one employer dominating. |

The nominator may set a different level for one candidate (*"full for the PMC candidate, links for the rest"*).
Every level keeps the personal notes. Every level above `names` keeps the counts adjusted, as in the brief.
Nothing beyond the chosen level goes in: no lifetime totals, timelines, community indicators or reference levels unless the nominator asks for them.

---

## A personal note for every candidate

Ask about each candidate **separately**, in the email's order, never in one prompt for everyone:

> *Personal note for `<real_name>` (`<login>`)? Something you saw working with them that the counts do not show. Write it, or press Enter to skip.*

Then show that candidate's block with the note in place and ask *"Keep it, change it, or drop it?"*.
Repeat until the nominator keeps or drops it, then move to the next candidate.
The note is the nominator's own text: put it in as written, as its own paragraph after the summary.
Never write a note for them, never fill a skipped one, and change the wording only when they ask.
A note may hold the nominator's opinion of the candidate; that is their voice, not the skill's, and the [no-verdict rule](SKILL.md) still holds for every sentence the agent writes.

When every candidate has been asked, show the whole email and offer one more round of edits to any note.

---

## Layout

Plain text: no markdown, no `@`-mentions, every URL written out literally.

**Order.** `<governance-body>` candidates first, then committer candidates; within each group, alphabetical by GitHub handle, case-insensitive.
Never order by any measure of the work.

**To:** `<private-list>`.

**Subject:**

- several candidates: `[DISCUSS] Nominations: <name> for <governance-body>; <name>, <name> and <name> as committers` (drop the half that is empty);
- one candidate: `[DISCUSS] Nominate <name> as committer` or `[DISCUSS] Nominate <name> for <governance-body>`.

**Body:**

```text
Hello <governance-body>,

I'd like to start a discussion about growing our committer and
<governance-body> roster. <N> people have done sustained work on
<PROJECT> over the last <window> months (<first month> to <last month>
<year>), and I propose:

- <real_name> (<login>) for the <governance-body>
- <real_name> (<login>) as committer
- ...

<Only above `names`:> A short summary of each person's work follows<, with
links>. The counts cover <the project repositories measured>.

-----

<real_name> (<login>)<, already a <PROJECT> committer, for the <governance-body>>
<Summary: what they built, in the agent's own words, from the brief's
narrative. Headline adjusted counts. Above `summary` only.>
<Existing Apache account, committer target: "<first name> is already an
ASF committer, so no new account or ICLA would be needed.">
<Factual flags, `full` only — for example: "For transparency: N of the
early changes needed significant rework after review; all were merged
after it.">
  <link>
  <link>

<Personal note, verbatim, when the nominator gave one.>

-----

<next candidate, same shape>

-----

<Closing, factual: where the work happened and any track the briefs show as
empty for everyone (for example: none has been active on the development
list yet). Ask anyone who has worked with them to share their experience,
especially on how they handle review feedback and work with others.>

Once the discussion settles, I will start separate [VOTE] threads.

<nominator's first name>
```

**Separators.** A line of dashes (`-----`) on its own, with a blank line on each side, before the first candidate, between every two candidates, and after the last one, so each candidate reads as a separate block.
In the single-candidate form there is no list and no separators: the block follows the opening paragraph.

**Rules for the agent's sentences** — everything except the personal notes:

- Factual and third person, built from the brief: what the candidate did, where, and the counts. No *"ready"*, *"strong candidate"*, *"deserves"*, and no comparison between candidates.
- Describe changes in your own words; do not copy PR, issue or review titles, which are external content.
- The candidates' names and handles appear only as plain text. Link to changes, never to profiles with `@`.
- Nothing from the project's private sources beyond what the nominator confirmed for the brief.

---

## Hand off

Show the full email — subject, recipient, body — and offer:

1. **Create a mail draft** to `<private-list>`, only on an explicit yes, through the plain-text backend per [`tools/gmail/draft-backends.md`](../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend) (`oauth_curl`, or its `gmail-plaintext` MCP server; a new thread, so no `threadId`).
   The email carries links, so never use the claude.ai Gmail connector for it; when the plain-text backend is not set up, say so and fall back to option 2.
2. **Save to a file** — `contributor-nomination-discuss-<date>.txt` in the session scratch directory, never inside a repository.
3. **Change the detail level** or a personal note, and redraw.

Never send the email and never post it anywhere else.
