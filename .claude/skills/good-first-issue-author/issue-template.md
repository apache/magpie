<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Good-first-issue body template

The skill renders a `suitable` candidate into this structure. Every
section is required: the readiness checklist
([`readiness-checks.md`](readiness-checks.md)) fails a draft that drops
one. Keep the whole body short. A good first issue a newcomer can read in
two minutes beats a thorough one they bounce off.

The title is rendered separately from the body. It must be a specific,
action-oriented imperative: `Add a --dry-run flag to the export command`,
not `Export improvements`.

```markdown
## Summary

One or two sentences: what to do, stated as an outcome a newcomer can aim
at. No project jargon that is not linked below.

## Background

Why this matters and the context a first-time contributor would not have.
Two to four sentences. Link the prior issue/PR/discussion if one exists.

## Where to look

The concrete starting point so the contributor does not have to hunt:

- `path/to/the/file.py` — the function or block to change.
- Related: `path/to/a/test.py` — where a test for this would live.

## Acceptance criteria

A checklist that tells the contributor exactly when they are done:

- [ ] <observable, checkable outcome>
- [ ] <a test covers the change, where the project expects tests>
- [ ] <docs/changelog updated, if the project requires it>

## Estimated effort

A rough band at or under the project's `max_effort_hours`, e.g.
"~1-2 hours for someone new to the codebase." Set expectations honestly.

## Getting started

The newcomer-onboarding link, drawn from `getting_started_link` (linked,
never paraphrased). One absolute-URL link to a "Your first contribution"
or equivalent section, not the top of the contributing doc.

<ai_attribution_footer>
```

## Rendering rules

- Substitute `<ai_attribution_footer>` with the literal markdown from the
  adopter config. Never invent attribution wording.
- Fill **Where to look** from the candidate's named files; if the
  candidate named none, the suitability gate should already have returned
  `needs-scoping` with `no-code-pointer`, so a draft never reaches here
  without at least one pointer.
- Keep **Acceptance criteria** observable. "Make it better" is not a
  criterion; "the command exits 0 and prints the count" is.
- Do not promise a reviewer's decision or a merge. The issue invites a
  contribution; a maintainer still reviews the PR.
