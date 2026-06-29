<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Comment templates

Every contributor-facing comment this skill posts comes from
this file. The templates exist to keep the teaching register
consistent across threads and to make tone review tractable —
the maintainer reviews the wording **here** once, not on every
PR.

Four canonical interventions are defined. The skill picks at
most one per invocation.

Placeholders:

- `<author>` — contributor's GitHub login (without `@`; the
  template adds it).
- `<doc_label>` — short link label resolved from
  `<project-config>/mentoring-config.md → convention_pointers`.
- `<doc_url>` — link target, same source.
- `<ai_attribution_footer>` — verbatim from
  `<project-config>/mentoring-config.md → ai_attribution_footer`.

If a template would render with a missing `<doc_label>` or
`<doc_url>` (because the trigger fired but the
`convention_pointers` row is incomplete), the skill aborts
before showing the maintainer. Do not post a half-rendered
comment.

---

## 1. Missing repro

**Trigger**: bug report or PR description that asserts a
problem without a way to reproduce it (no minimal example, no
stack trace, no command, no input data shape).

```markdown
@<author> — to take a look at this we'll need a way to reproduce it. Could you add:

1. The smallest example that triggers the behaviour (a few lines of code, or the exact command + input).
2. What you expected to happen versus what actually happened.

[<doc_label>](<doc_url>) walks through the format we look for.

<ai_attribution_footer>
```

## 2. Missing version

**Trigger**: bug report that omits the version of the project
the contributor is running.

```markdown
@<author> — could you add the version you're running? [<doc_label>](<doc_url>) shows where to find it. Knowing the version tells us whether this is a known regression or new ground.

<ai_attribution_footer>
```

## 3. Convention pointer

**Trigger**: PR or issue where the contributor is missing a
piece of repo convention they could have found themselves
(commit-message format, PR-title prefix, where tests go,
required changelog entry, etc.).

```markdown
@<author> — heads up, this repo has a convention for that: [<doc_label>](<doc_url>). Once you align with it a maintainer can take the next look.

<ai_attribution_footer>
```

## 4. Why-question

**Trigger**: contributor pushes back on a maintainer's existing
review comment with "why does this need X?" and the answer is
in public documentation. The skill answers **once**; if the
contributor disagrees, the skill hands off (see
[`hand-off.md`](hand-off.md)).

```markdown
@<author> — that's covered here: [<doc_label>](<doc_url>). The short version is in the first paragraph. If after reading you still think it shouldn't apply to this PR, drop a comment and a maintainer will weigh in.

<ai_attribution_footer>
```

---

## What is deliberately not a template

Listed so reviewers see the choices and can push back.

- **Greeting + welcome**. The first message in a contributor's
  PR thread is often a maintainer's, not the agent's. The
  agent posting "welcome to the project!" before the
  maintainer has the chance is rude and cuts the maintainer
  out of the relationship. If a project wants a welcome
  comment, that is a triage-level concern, not a Agentic Mentoring
  concern.
- **Closing comment**. The skill never posts on a thread it is
  about to close — closing belongs to triage. If the
  contributor's submission is out of scope or duplicate, the
  skill exits without commenting and lets
  [`pr-management-triage`](../pr-management-triage/SKILL.md)
  handle the close.
- **Approval / "looks good"**. Agentic Mentoring does not signal review
  outcomes. Even a casual "this looks like a good direction"
  shifts contributor expectations.
  [`pr-management-code-review`](../pr-management-code-review/SKILL.md)
  owns that surface.
- **Praise**. "Great question!", "Thanks for the
  contribution!", "Awesome work" — all noise. They train the
  contributor to skim the rest of the comment. The
  [`tone-checks.md`](tone-checks.md) checklist rejects any
  draft containing them.
