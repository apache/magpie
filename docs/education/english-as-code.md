<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [English as a programming language](#english-as-a-programming-language)
  - [Words used on this page](#words-used-on-this-page)
  - [The shift in one picture](#the-shift-in-one-picture)
  - [Precision still matters, it just moves](#precision-still-matters-it-just-moves)
  - [Ambiguity is the new class of bug](#ambiguity-is-the-new-class-of-bug)
  - [Because it's code, treat it like code](#because-its-code-treat-it-like-code)
  - [The compiler is fuzzy, so you test harder](#the-compiler-is-fuzzy-so-you-test-harder)
  - [Why this framing is worth keeping](#why-this-framing-is-worth-keeping)
  - [Check your understanding](#check-your-understanding)
  - [How this connects to the other guides](#how-this-connects-to-the-other-guides)
  - [Licence](#licence)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# English as a programming language

By now you have worked with an agent, chosen a model, written a skill, tested it
with evals, and let it run on its own. This page steps back to name the idea
underneath all of it, the mental shift that makes the whole craft click.

Here it is: when you build with agents, **the words you write are the program**.
The English (or any natural language) in your prompts and skills is not
documentation *about* the code. It *is* the code. Once that lands, a lot of the
advice in this stream stops feeling like a list of tips and starts feeling like
one coherent discipline.

## Words used on this page

New to some of these words? Here is what they mean here. The
[landing page](README.md) has a fuller list.

- **Skill**: a Markdown file of instructions the agent follows to do one job.
- **Prompt**: the written instructions you give the model.
- **Specification**: a precise description of what a program should do. In this
  world, your prose *is* the specification the agent executes.
- **Ambiguity**: room for more than one reading. In ordinary writing it is
  harmless; in an instruction to an agent it is a bug.
- **Eval**: a repeatable test of the agent's output, used because the output can
  vary.

---

## The shift in one picture

| Traditional programming | Programming with English |
|---|---|
| You write code in a formal language | You write instructions in natural language |
| The compiler is exact and unforgiving | The model is flexible and interprets |
| A typo fails loudly | A vague phrase fails *quietly*, by doing something plausible but wrong |
| You debug logic | You debug *wording and ambiguity* |
| Tests give a yes or no | Evals give a distribution, better or worse across many inputs |

The middle column is where twenty years of habit lives. The right column is the
new craft. Neither is harder; they fail differently, and you debug them
differently.

## Precision still matters, it just moves

A beginner's hope is that natural language means you can be vague and the model
will "just get it". The opposite is true. Because the model *will* act on
whatever you wrote, imprecise words produce imprecise behaviour, and, worse, they
fail quietly. A compiler rejects a typo with an error. A model reads a woolly
instruction and does something *reasonable-looking* that is not what you meant,
and you may not notice until it matters.

So precision does not go away when you write in English. It moves from *syntax*
to *meaning*. Compare:

> *"Handle old issues."*

against:

> *"An issue is 'stale' if it has had no comment for 90 days and carries no
> `pinned` label. For each stale issue, draft (do not post) a comment asking
> whether it is still relevant."*

The second leaves the model far less to invent. Every ambiguity you remove is a
decision you made instead of one the model made for you. Writing for an agent is
the discipline of hunting down ambiguity and closing it.

## Ambiguity is the new class of bug

In ordinary prose, "review the recent changes" is a perfectly clear sentence. As
an instruction to an agent it hides at least three bugs. *Recent* since when?
*Review* how, meaning read them, critique them, or summarise them? *The changes*
to what? Each unstated answer is a place the agent will guess, and it may guess
differently on Tuesday than it did on Monday.

This is why so much of good skill-writing is really *disambiguation*:

- **Define your terms.** If a word carries a specific meaning ("stale", "ready",
  "trivial"), say what it means, don't assume.
- **Say what "done" looks like.** A concrete example of a good output removes a
  whole category of guessing.
- **State the boundaries.** What should the agent *not* do? Where does it stop?
- **Name the edge cases.** Empty input, malformed input, and the "looks like X
  but is really Y" case. Spell out what to do, or the model will improvise.

## Because it's code, treat it like code

If prose is the program, then everything you already do to keep code healthy
applies, and Magpie leans into exactly this:

- **Review it.** Skills and prompts are read and critiqued by another person
  before they land, the same as any code (PRINCIPLE 14). A reviewer reads the
  *words* for ambiguity and missing cases, not just for typos.
- **Version it.** Prompts live in the repository, in git, with a history. A change
  in wording is a change in behaviour, and the history tells you when behaviour
  moved and why.
- **Test it.** You cannot compile a prompt, but you can run it against examples.
  That is what an [eval suite](eval-driven-development.md) is: the test suite for
  code written in English. It is required precisely because the "compiler" here
  never rejects a bad instruction for you (PRINCIPLE 8).
- **Keep it DRY and composable.** One skill, one job; shared rules live in one
  place and are pointed to, not copied. Duplicated prose drifts apart exactly the
  way duplicated code does.

## The compiler is fuzzy, so you test harder

The deepest consequence of this idea is that your "compiler", the model, is
*probabilistic*. Give it the same instruction twice and it may act slightly
differently each time. A real compiler is deterministic, so passing once means
passing forever. A model is not, so a single successful run tells you almost
nothing.

That is the whole reason this stream gives evals their own step. When the language
you program in is executed by something that interprets rather than computes, the
only way to know your program works is to run it over many representative inputs
and judge the results as a whole. Evals are not an add-on to programming in
English; they are the part that makes it *engineering* instead of hoping.

## Why this framing is worth keeping

Hold onto "the words are the program" and the rest of the craft organises itself:

- Vague prompt giving odd results? That is a **bug in your spec**, not a flaky
  tool, so go tighten the words.
- Wondering whether a wording change is safe to ship? **Run the evals**, the same
  as you would run tests on a refactor.
- Tempted to paste a rule into three skills? That is **copy-paste code smell**,
  so point to one shared source instead.
- Reviewing someone's skill? You are **reviewing code**, so read for ambiguity,
  missing edge cases, and unstated assumptions.

The tools are new. The engineering instincts are the ones you already have. This
page is just the bridge that lets you reuse them.

## Check your understanding

- Where does "precision" go when you program in English, and why does vagueness
  fail more quietly than a syntax error?
- Why is ambiguity a *bug* here rather than a harmless feature of prose?
- Why can't a single successful run tell you a prompt "works"?

## How this connects to the other guides

- **[How to write your first skill](your-first-skill.md)** is this idea in
  practice: a skill is a program written in English.
- **[Eval-driven development](eval-driven-development.md)** is the testing half of
  the discipline, and the reason "it ran once" is not enough.
- **[Pattern catalogue](pattern-catalogue.md)** is the reusable-code library for
  this language: vetted blocks you compose instead of rewriting.
- **[How to contribute to Magpie](contributing.md)** is where you put it to work,
  because contributing to Magpie *is* programming in English.

## Licence

Everything in `docs/education/` is under the Apache License 2.0 (PRINCIPLE 17).
Pages written with help from AI carry a `Generated-by:` note in their commit
message, following ASF Generative Tooling Guidance.
