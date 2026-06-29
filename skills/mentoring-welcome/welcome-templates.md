<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Welcome comment templates

Two canonical welcome-comment bodies rendered by the
`mentoring-welcome` skill: one for issues and one for PRs. The skill
substitutes `<author>`, `<contributing_guide_url>`,
`<code_of_conduct_url>`, and (for issues) `<good_first_issue_url>`
from `<project-config>/mentoring-welcome-config.md` before showing the
draft to the maintainer.

`<welcome_note>` is the optional project-specific sentence from
`welcome_note_issue` or `welcome_note_pr`. Omit this line if the key is
absent or empty. The `<ai_attribution_footer>` is appended verbatim from
the adopter config; do not include literal footer text here.

---

## Issue welcome

```markdown
@<author> — welcome, and thanks for filing this issue.

Here's what to expect next:

1. A maintainer will read through the report and may ask follow-up
   questions. Responding promptly keeps the thread moving.
2. Once the issue is understood, it will be triaged (labeled and
   prioritised) within the project's usual triage window.

If you'd like to work on it yourself, check the
[contributing guide](<contributing_guide_url>) for the development
setup and the conventions the project uses. We also maintain a
[good first issues list](<good_first_issue_url>) if you'd prefer a
task with a clearer scope to start.

Our [community norms](<code_of_conduct_url>) cover how we interact in
this space — worth a one-minute read.

<welcome_note>

<ai_attribution_footer>
```

---

## PR welcome

```markdown
@<author> — welcome, and thanks for opening this PR.

Here's what to expect next:

1. A maintainer will review the diff. Reviews can take a few days
   depending on queue depth; a ping on the thread after a week is
   fine if there has been no response.
2. If changes are requested, address them in new commits and leave the
   resolution comments on the review thread rather than editing the
   original comment — that keeps the review history readable.

The [contributing guide](<contributing_guide_url>) covers the commit
format, test expectations, and changelog requirements the project uses.
Our [community norms](<code_of_conduct_url>) are also worth a quick read.

<welcome_note>

<ai_attribution_footer>
```

---

## Rendering notes

- `<author>` is the GitHub login of the thread opener, without the `@`
  prefix in substitution — the template already includes the `@`.
- `<good_first_issue_url>` appears only in the **issue** template. If
  `good_first_issue_url` is absent from the adopter config, remove the
  entire "good first issues list" sentence before rendering.
- `<welcome_note>` and the blank line before `<ai_attribution_footer>`
  are dropped if the adopter has not configured `welcome_note_issue` /
  `welcome_note_pr`.
- Do not reword or expand the numbered steps. The steps are intentionally
  minimal: the contributing guide is the authoritative source; the welcome
  points there and steps aside.
- The tone follows the Agentic Mentoring spec:
  [`docs/mentoring/spec.md`](../../docs/mentoring/spec.md#teaching-register--tone-guide).
  Patient, specific, short. No praise, no hedging, no AI self-reference
  outside the footer.
