<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [How to contribute to Magpie](#how-to-contribute-to-magpie)
  - [Words used on this page](#words-used-on-this-page)
  - [What a contribution looks like here](#what-a-contribution-looks-like-here)
  - [Magpie is built spec-first](#magpie-is-built-spec-first)
  - [The framework's rules apply to your contribution too](#the-frameworks-rules-apply-to-your-contribution-too)
  - [The path to a merged change](#the-path-to-a-merged-change)
  - [Where to get help](#where-to-get-help)
  - [Check your understanding](#check-your-understanding)
  - [How this connects to the other guides](#how-this-connects-to-the-other-guides)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# How to contribute to Magpie

This is the last page of the progression, and it turns everything before it into
action. You now know what an agent is, how to work with one, how to pick a model,
how to write a skill and test it with evals, how autonomy works, and why the
words you write *are* the program. This page is about giving that work back,
contributing to Magpie itself.

Magpie is the open, project-agnostic framework for agent-assisted maintainership.
It grows the way any healthy open-source project grows: from people who used it,
saw something missing or wrong, and sent a change. This page is the on-ramp for
becoming one of those people. It is a friendly overview; the authoritative
reference is [`CONTRIBUTING.md`](../../CONTRIBUTING.md), which you should read in
full before your first patch.

## Words used on this page

New to some of these words? Here is what they mean here. The
[landing page](README.md) has a fuller list.

- **Framework**: Magpie itself, meaning the shared skills, tools, and docs, as
  opposed to your own project that *adopts* it.
- **Skill**: a Markdown file that tells the agent how to do one job. Contributing
  a skill is the most common first contribution.
- **Eval**: the test suite for a skill. A skill contribution is not finished
  without one.
- **Spec**: a precise description of what part of the framework should do. Magpie
  is built spec-first (see below).
- **Pull request (PR)**: the change you offer to the project for review before it
  is merged.

---

## What a contribution looks like here

Magpie is unusual: most of it is written in English, not in a formal language.
So most contributions are *prose that the agent executes*, such as a new skill, a
fix to an existing skill, a pattern for the [catalogue](pattern-catalogue.md), or
a page in this very stream. That is a feature, not a quirk: it means you can
contribute meaningfully without being a systems programmer, as long as you can
think clearly and write precisely. The [English as a programming
language](english-as-code.md) page is the mindset; this page is the mechanics.

Good first contributions, roughly in order of on-ramp:

- **Fix or sharpen a skill.** You ran a skill, and it drifted or missed a case.
  Tighten the wording and add an eval case that captures what you saw.
- **Improve the docs.** A confusing sentence in this stream, a missing example, a
  broken link. Small, valuable, and a gentle way to learn the process.
- **Add a pattern.** You found a skill shape that works well; write it up for the
  [pattern catalogue](pattern-catalogue.md) so others can copy it.
- **Write a new skill.** The biggest of the common first contributions.
  [Your first skill](your-first-skill.md) is the step-by-step path, and it ends
  at an open pull request.

## Magpie is built spec-first

One thing to understand before you dive in is that Magpie is developed
**spec-first**. The framework keeps a set of *specifications*, which are precise
descriptions of what each area should do, and the code and docs are reconciled
against them. A build loop (`tools/spec-loop/`) can even drive that reconciliation
with an agent, one work item at a time. The full write-up is
[`docs/spec-driven-development.md`](../../docs/spec-driven-development.md).

What this means for you as a contributor:

- **A change that alters behaviour usually starts with the spec.** If you are
  adding or changing what a part of the framework *does*, the matching spec in
  `tools/spec-loop/specs/` is the source of truth to update first, so the
  description and the implementation never drift apart.
- **The spec is where "what it should do" lives; the code and docs are where
  "how" lives.** Keeping them in step is a core habit here, the same instinct as
  keeping tests in step with code.
- **Small doc or wording fixes** do not need a spec change, but anything that
  changes a rule, a flow, or a contract does.

You do not need to master the spec loop to make your first contribution. You do
need to know it exists, so your change lands in step with the specs rather than
fighting them.

## The framework's rules apply to your contribution too

Everything this stream taught about *building* safely also governs what you
*contribute*. A reviewer will check that your change keeps the framework's
posture:

- **External content is data, not instructions** (PRINCIPLE 0). A skill you add
  must treat issue bodies, PRs, and mail as data, and ship an eval case proving
  it.
- **Propose, confirm, act** (PRINCIPLE 6). A skill's world-changing steps are
  proposals a maintainer confirms, never silent actions.
- **Project-agnostic placeholders** (PRINCIPLE 12). No real project name in the
  text; use `<PROJECT>`, `<tracker>`, `<upstream>`, `<security-list>`.
- **Evals are required** (PRINCIPLE 8). A skill without a matching eval suite is
  not finished, and a PR that adds one without evals will not pass review.
- **Apache-2.0, and mark AI help** (PRINCIPLE 17). Contributions land under the
  framework licence; AI-authored contributions carry a `Generated-by:` token in
  the commit message, per ASF Generative Tooling Guidance.

These are not hoops. They are the same habits the whole stream has been teaching,
now on the other side of the pull request.

## The path to a merged change

The short version (the long version is [`CONTRIBUTING.md`](../../CONTRIBUTING.md)):

1. **Get set up.** Clone the framework repository and confirm you can run `uv`
   and the validators. See [`CONTRIBUTING.md`](../../CONTRIBUTING.md) and
   [`docs/prerequisites.md`](../prerequisites.md).
2. **Make the smallest change that stands on its own.** One skill, one fix, one
   page. Small changes are reviewed and merged faster.
3. **Update the spec if behaviour changes.** For anything beyond a wording fix,
   update the matching `tools/spec-loop/specs/` entry.
4. **Run the validators locally.** The same checks CI runs: the skill/tool
   validator, the spec validator, markdownlint, and the link check. Running them
   first saves a round-trip.
5. **Open the pull request.** Say what the change does, what you tested, and what
   a reviewer should look at closely. A clear description speeds review.
6. **Work with the review.** A reviewer reads your prose the way they would read
   code, checking for ambiguity, missing edge cases, and unstated assumptions.
   Treat that as the collaboration it is.

## Where to get help

- Read [`CONTRIBUTING.md`](../../CONTRIBUTING.md) end to end before your first
  patch. It is the authoritative process, layout, and dev-loop reference.
- Use the [`magpie-write-skill`](../../skills/write-skill/SKILL.md) skill
  (`/write-skill`) for the complete skill-authoring checklist.
- Read [`MISSION.md`](../../MISSION.md) and [`PRINCIPLES.md`](../../PRINCIPLES.md)
  for the *why* behind the rules a reviewer will apply.

## Check your understanding

- Why can you contribute meaningfully to Magpie without being a systems
  programmer?
- When does a contribution need a spec change, and when does it not?
- Which framework rules will a reviewer check on a skill you contribute?

## How this connects to the other guides

- **[Your first skill](your-first-skill.md)** is the concrete zero-to-merged path
  this page frames; start there for a skill contribution.
- **[English as a programming language](english-as-code.md)** is the mindset that
  makes contributing to Magpie approachable.
- **[`CONTRIBUTING.md`](../../CONTRIBUTING.md)** is the authoritative contribution
  reference, covering process, repository layout, and the dev loop CI enforces.
- **[`docs/spec-driven-development.md`](../../docs/spec-driven-development.md)** is
  the spec-first workflow the framework is built on.

## Licence

Everything in `docs/education/` is under the Apache License 2.0 (PRINCIPLE 17).
Pages written with help from AI carry a `Generated-by:` note in their commit
message, following ASF Generative Tooling Guidance.
