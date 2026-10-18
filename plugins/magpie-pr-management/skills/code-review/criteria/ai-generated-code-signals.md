<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# AI-generated code signals

Read the source section the adopter's `Section anchors` table links for this category (`section_anchors` in the `context` output) and quote the rule **verbatim** in the finding — never paraphrase. If the category has no anchor row, use a plain reference and surface the missing anchor once at the top of the review.

`code-review context` ran the authorship-disclosure check (`ai_disclosure`): it fires only when the project's PR template (or criteria file) asks for a disclosure, the body carries AI-authorship signals, and no disclosure is affirmed — a `minor` finding, never a slop signal, never gating an otherwise-approvable PR on its own. The adopter's own AI-generated-code rules (fabricated APIs, placeholder stubs) are read from the source and judged from the diff.

The "AI-generated code signals" category is primarily driven by the adopter's
source files. The following is a **framework-level default** that applies
regardless of adopter-specific rules.

Some projects require contributors to **disclose** when generative-AI tooling
helped author a PR — typically a checkbox or `Generated-by:` line in the PR
template, or a rule in the contributing docs. This is project policy, not a
framework universal: this default fires **only when the project itself has
such a requirement**. Where it does not, there is nothing to enforce and no
finding is raised.

**Determine whether the project requires disclosure from the repository
itself, not from a hardcoded list.** Read the repo's
`.github/PULL_REQUEST_TEMPLATE.md` (and any `.github/PULL_REQUEST_TEMPLATE/`
variants) for a generative-AI / authorship disclosure section, or an adopter
`pr-management-code-review-criteria.md` entry that declares one. If neither
exists, skip this check entirely.

**Scan the PR body for AI-authorship signals** (case-insensitive). Any one is
enough to treat the body as likely AI-authored:

- a task-list "Test plan" / "Test Plan" section using `- [x]` / `- [ ]`
  checkboxes;
- structured `## Summary` / `## Changes` / `## Test plan` headings that
  **replace** the project's PR template rather than filling it in;
- an echoed `**Title:**` / `**Summary:**` line restating the PR title;
- a `Generated-by:` / `Co-Authored-By:`-an-AI-tool trailer, a
  "🤖 Generated with …" line, or first-person tool phrasing
  ("I (Claude / Cursor / Copilot / Devin / …) …").

**Raise a `minor` finding** when AI-authorship signals are present **and** the
project requires disclosure **and** the body carries no affirmed disclosure
(the template's disclosure checkbox is absent or left unchecked, and no
`Generated-by:` line is present). Cite the specific signal and quote the
project's own disclosure requirement:

> `minor` — *"This PR looks co-authored with generative-AI tooling
> (cite the signal — e.g. a `Test plan` task-list and a dropped PR template),
> but the project's AI-assistance disclosure is missing or left unchecked.
> The project asks contributors to affirm AI assistance — please tick the
> disclosure box / add the `Generated-by:` line per the project's
> contributing-docs link."*

This is **not** slop and is deliberately **not** a
[`slop-detection.md`](../classifications/slop-early-exit.md) signal — a genuine, useful PR can
simply have skipped the disclosure. Keep it a `minor`
contribution-guidelines observation inside the normal review; it must never
gate an otherwise-approvable PR on its own, and it never triggers the slop
early-exit path. The operational scan that produces this finding runs in
[`review-flow.md` § AI-authorship disclosure scan](../review-flow.md#step-3--read-the-pr-body-and-acceptance-criteria).

---
