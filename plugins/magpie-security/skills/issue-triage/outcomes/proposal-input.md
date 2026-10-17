<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-triage — `render-proposal` input

Read from [`SKILL.md` Step 4](../SKILL.md#step-4--compose-proposal-comment).
Write one JSON file per tracker with the Write tool, then run `<sm> render-proposal --input <file>`.
The prose fields are the agent's; the tool only lays them out, checks them and links them.

| Field | What it holds |
|---|---|
| `tracker`, `number`, `scratch` | `<tracker>`, the issue number, the scratch directory (the comment file is `<scratch>/triage-<N>.md`). |
| `class` | One of the six classes, or `UNCERTAIN` with `tentative_class`: the comment then opens with *"Low-confidence proposal, please challenge."* before the class line, per [`classification.md`](../classification.md#confidence-and-edge-cases). |
| `summary` | The one-paragraph technical summary, with the 2–3 sentence verbatim Security Model quote and its linked anchor ([Step 2.5](../security-model-and-precedents.md#step-25--apply-the-security-model-verbatim)) and any `precedent-signal` citations. |
| `severity` | A qualitative guess (*"my read is Medium-ish, team-scoring expected"*); a CVSS score, vector or `N/10` is refused. |
| `open_question` | The load-bearing open question the team scores after; omit when there is none. |
| `fix_shape` | The fix in one or two sentences, or the "why not" framing for INVALID / INFO-ONLY. DEFENSE-IN-DEPTH gains *"defense-in-depth fix is welcome via public PR; not a CVE."* when the text lacks it. |
| `action_items` | A list: two or more render as a numbered list, one as a sentence. |
| `handles`, `question` | The `<sm> mentions` picks (at most 3, on the roster, never the triager) and the question they are best placed to answer. |
| `roster`, `viewer`, `names` | The Step 0 roster handles, the triager's login, and the display name → handle map the bare-name scrub uses. |
| `canned_heading`, `canned_headings` | INFO-ONLY: the exact heading, checked against the headings of `canned-responses.md`. |
| `kept_tracker` | PROBABLE-DUP: the tracker to keep; the comment names `security-issue-deduplicate <N> <kept>`. |
| `upstream`, `prs` | FIX-ALREADY-PUBLIC: each candidate PR's `number`, `author`, `state` and `date`; the reporter-reply draft of [`classification.md`](../classification.md#fix-already-public) is rendered from them, `merged` or `open since` per PR. |

The output carries `text`, `file`, `command` (`gh issue comment <N> --repo <tracker> --body-file <file>`), `replacements_made`, `linked_refs` and `unlinked_cves`.
`unlinked_cves` must be empty: link those CVE IDs in the prose per [`AGENTS.md`](../../../../../AGENTS.md#linking-cves) and render again.
A refusal exits `2` with `refused`: fix the input, never the rendered text.
