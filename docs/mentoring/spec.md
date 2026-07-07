<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Mentoring (spec)](#mentoring-spec)
  - [Status](#status)
  - [Scope](#scope)
  - [Triggers](#triggers)
  - [Teaching register — tone guide](#teaching-register--tone-guide)
    - [Voice](#voice)
    - [Forbidden](#forbidden)
    - [AI-attribution footer](#ai-attribution-footer)
  - [Hand-off protocol](#hand-off-protocol)
  - [Adopter contract](#adopter-contract)
  - [Resolved design decisions](#resolved-design-decisions)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Mentoring (spec)

## Status

Experimental. Seven skills shipped:

| Skill | Purpose |
|---|---|
| [`pr-management-mentor`](../../skills/pr-management-mentor/SKILL.md) | Draft a teaching-register comment on a single GitHub issue or PR thread. |
| [`good-first-issue-author`](../../skills/good-first-issue-author/SKILL.md) | Draft a single net-new good first issue from a maintainer-supplied candidate. |
| [`mentoring-welcome`](../../skills/mentoring-welcome/SKILL.md) | Draft a first-contact orientation comment for a first-time contributor on a newly opened issue or PR. |
| [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Read-only readiness tracker mapping a contributor's GitHub activity against the adopter's declared committer/PMC thresholds. |
| [`good-first-issue-sweep`](../../skills/good-first-issue-sweep/SKILL.md) | Sweep the open issue backlog for issues that could be labelled as good first issues, scoring each against the G1–G7 suitability rubric. |
| [`onboarding-concierge`](../../skills/onboarding-concierge/SKILL.md) | Answer a newcomer's "how do I contribute here" question from the project's `CONTRIBUTING.md`; classifies the question and hands off to a human for design, security, or out-of-scope queries. |
| [`newcomer-issue-explainer`](../../skills/newcomer-issue-explainer/SKILL.md) | Explain an open good-first-issue in beginner terms and sketch a concrete approach (file pointers, done-definition, where to ask); an assessment gate declines closed, security-sensitive, or scope-unclear issues; nothing is posted without maintainer confirmation. |

This document is the normative Agentic Mentoring spec: tone guide, hand-off
protocol, and adopter contract. The skills implement these conventions;
the spec is the authoritative reference when the two diverge.
See [`MISSION.md` § Agentic Mentoring](../../MISSION.md#technical-scope) and
[`docs/modes.md` § Mentoring](../modes.md#mentoring).

## Scope

Agentic Mentoring joins issue and PR threads in a teaching register. The
agent's job is to lower the barrier to a contributor's *next
useful action*. Concretely, in scope:

- **Clarifying questions** when the contributor's first message
  is ambiguous (missing repro, missing version, missing intent),
  so a human reviewer's first read is a productive one.
- **Pointers to project conventions** with a direct link, when
  the contributor is missing a piece of repo context they could
  have found themselves but did not.
- **Explanation of *why*** a request was made, when the
  contributor pushes back on a maintainer's review comment ("why
  does this need a test?", "why split the PR?").
- **Paired examples from prior PRs** when a similar pattern has
  shipped before and a one-line link saves the contributor
  several hours.
- **Hand-off** to a human when the question exceeds what an
  agent should answer (architectural taste, security-sensitive
  design, deprecation timing, anything embargoed).

Out of scope:

- *Reviewing code*. That is Agentic Triage's
  [`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md)
  skill. Agentic Mentoring does not approve, request changes, or post inline
  diff comments.
- *Triage routing*. That is Agentic Triage's
  [`pr-management-triage`](../../skills/pr-management-triage/SKILL.md)
  skill. Agentic Mentoring does not assign labels, mark draft, or close PRs.
- *Authoring fixes*. That is Agentic Drafting. Agentic Mentoring does not open PRs or
  edit code.
- *Speaking for the maintainer team* on disputed decisions. Agentic Mentoring says "a maintainer will weigh in" and stops.

## Triggers

Agentic Mentoring never posts unprompted on a thread it has not been
invoked on. The skill is opt-in per invocation. Three trigger
paths:

1. **Maintainer-on-demand**. A maintainer runs
   `/magpie-pr-management-mentor <pr-number>`. The skill
   reads the thread, decides whether a mentoring intervention is
   warranted, drafts the comment, and waits for the maintainer
   to confirm before posting.
2. **First-contact filter**. After
   [`pr-management-triage`](../../skills/pr-management-triage/SKILL.md)
   classifies a PR as "first contributor, missing repro" (or
   equivalent triage flag), the maintainer can chain
   `/magpie-pr-management-mentor` on that PR. The two skills compose;
   Agentic Mentoring does not run inside Agentic Triage by default.
3. **Issue-thread invocation**. Same opt-in, on issues rather
   than PRs, for the "missing version / missing repro" case.

Why no auto-fire: posting a teaching-register comment without
explicit human authorization risks the agent talking past a
maintainer who is mid-conversation with the contributor, or
posting on a thread where the maintainer has *deliberately* not
replied yet. Auto-fire is a Agentic Autonomous-shaped problem and inherits
Agentic Autonomous's sequencing constraint.

## Teaching register — tone guide

The contributor is the audience, not the maintainer. The
agent's voice is **patient, specific, and short**. It is not
formal. It does not lecture. It does not perform empathy. The
reader should leave the comment knowing what to do next, not
feeling managed.

### Voice

- **First line states the action**, not the meta. "Could you add
  the version you're running? Find it via …" not "I noticed
  your issue and would love to help by asking a clarifying
  question."
- **Link, don't quote**. Pointers to docs go as a single inline
  link with a short label. Do not paste the docs back at the
  contributor.
- **One ask per comment**. If the contributor is missing three
  things, ask for them as a numbered list, not three sequential
  paragraphs.
- **No hedging**. "This is a known pattern, see PR #1234" not
  "It seems like this might possibly be similar to PR #1234,
  although I'm not certain". The hedge tax falls on the
  contributor, who then has to decide how seriously to take the
  pointer.

### Forbidden

- Praise without specificity. "Great question!" and "Thanks for
  the contribution!" are noise. They train the contributor to
  skim.
- Restating the contributor's message back to them. "So what
  you're saying is …" — the contributor knows what they said.
- AI self-reference outside the attribution footer. The footer
  says it once; the body should not.
- Speaking for the maintainer. "The maintainers will probably
  want X" — Agentic Mentoring does not predict maintainer decisions. It
  says "a maintainer will reply on this; in the meantime,
  here's the convention" and stops.

### AI-attribution footer

Every contributor-facing comment ends with the same footer
convention used by
[`pr-management-triage/comment-templates.md`](../../skills/pr-management-triage/comment-templates.md),
adjusted to name the mentoring step rather than the triage
step. The expansion lives in the adopter's
`<project-config>/mentoring-config.md → ai_attribution_footer`.

The footer is non-negotiable: it calibrates the contributor's
trust (AI-drafted, may be wrong) and points at the project's
documented two-stage process.

## Hand-off protocol

The agent bows out and pings a human when:

1. The contributor pushes back on a substantive design point.
   Agentic Mentoring answers "why is this convention" once. If the
   contributor disagrees, Agentic Mentoring does not argue; it pings the
   maintainer.
2. The question touches security, embargoed work, deprecation
   timing, or anything not covered by public documentation.
   Agentic Mentoring does not improvise on these surfaces.
3. The thread reaches `<max_agent_turns>` (configurable, default
   2). After that the agent stops engaging on the thread
   regardless of content.
4. The contributor explicitly asks for a human ("can a
   maintainer look at this?").

The hand-off is one comment: a `@`-mention of the configured
maintainer team, a one-line summary of the open question, and
the agent's silence afterwards. The agent does not summarise
the conversation; the maintainer reads the thread.

## Adopter contract

Per-project values live in `<project-config>/mentoring-config.md`.
See the template at
[`projects/_template/mentoring-config.md`](../../projects/_template/mentoring-config.md).
Required keys:

| Key | Purpose |
|---|---|
| `mentoring_invocation_command` | Slash-command name (e.g. `/magpie-pr-management-mentor`). |
| `maintainer_team_handle` | `@<org>/<team>` mentioned on hand-off. |
| `ai_attribution_footer` | Literal footer markdown. Mirrors the triage-footer convention. |
| `convention_pointers` | Table of `{trigger phrase} → {docs link, one-line label}` so the agent links rather than paraphrases. |
| `max_agent_turns` | Integer, default 2. Hard ceiling on consecutive agent comments per thread. |
| `out_of_scope_topics` | Explicit list of topics on which the agent always hands off (security, deprecation, license, etc.). |

## Resolved design decisions

These questions were open before the skills shipped. The answers are
fixed in the shipped implementations.

- **GitHub-only.** `pr-management-mentor` posts to GitHub threads
  only. Mailing-list mentoring stays with the human maintainer; the
  agent has no list-subscriber identity.
- **Attribution footer.** Same wording as the triage footer, different
  step token (`mentoring` vs `triage`). One contributor-trust
  calibration is easier to reason about than two.
- **Every draft reviewed.** Every Agentic Mentoring comment requires explicit
  maintainer confirmation before posting. Pre-authorization is
  Agentic Autonomous-shaped and inherits Agentic Autonomous's sequencing constraint.

## Cross-references

- [`MISSION.md` § Agentic Mentoring](../../MISSION.md#technical-scope) —
  the mode definition + responsible-AI framing.
- [`docs/modes.md` § Mentoring](../modes.md#mentoring) —
  current implementation status (experimental, 7 skills shipped).
- [`.claude/skills/pr-management-triage/comment-templates.md`](../../skills/pr-management-triage/comment-templates.md) —
  tone-footer convention; `pr-management-mentor` mirrors its
  format with a `mentoring` step token.
- [`AGENTS.md`](../../AGENTS.md) — repository-level rules every
  mode inherits.
