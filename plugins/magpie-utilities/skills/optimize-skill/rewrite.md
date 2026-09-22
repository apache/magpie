<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Rewriting a skill with the maintainer

The passes in [`patterns.md`](patterns.md) move text without changing a
word of it. This one changes the words, so the maintainer writes them —
the agent's job is to carry the paragraphs, notice what the maintainer
keeps doing, and do it to the paragraphs that follow.

Run it when a skill is verbose rather than badly structured: the steps
are right, the prose is twice as long as it needs to be.

## How a pass goes

Work through the target's paragraphs in reading order, one per turn.
Never batch them: the point is to learn from each edit before showing
the next paragraph.

For each paragraph:

1. **Show it in a fenced block on its own.** Nothing else in the
   message but a one-line note of where it sits (`Step 3, paragraph 2
   of 4`) and what, if anything, you would change and why — one
   sentence, not a lecture.
2. **Wait.** The maintainer edits it and pastes it back, or says keep,
   cut, or asks you to draft it.
3. **If they rewrote it**, take their version verbatim. Do not
   re-edit it, do not "tidy" it afterwards. Their words are now the
   target's words.

A fenced block is as close as this gets to handing the text over: an
agent cannot put text into the maintainer's input line. On a terminal,
`/copy` lifts the block to the clipboard, which is usually faster than
selecting it.

Two things make this cheap to run: show the paragraph and stop, and
keep your own commentary to the one sentence. A maintainer rewriting
forty paragraphs will not read forty explanations.

## Learning as you go

After each rewrite, compare their version with yours and name the
change in one short line — *"cut the rationale, kept the rule"*, *"second
person, not imperative"*, *"dropped the cross-reference"*. Say it back so
they can correct a wrong reading immediately, and add it to a running
list.

From the next paragraph on, apply every rule on that list **before**
showing it. The paragraph the maintainer sees should already look the
way their last three edits implied. When two rules conflict, the more
recent one wins, and say so.

Watch for the same edit landing three times without being named. That
is a rule you have not spotted yet: state it, then apply it.

Do not infer a rule from a single edit that could as easily be about
that paragraph's subject. Wait for it to repeat. A rule invented from
one data point will be applied to thirty paragraphs before anyone
notices.

## Writing the rules down

At the end of the session, turn the running list into rules that will
mean something to a reader who was not there.

Generalise: *"said 'the skill decides' instead of 'the agent
determines'"* becomes *"prefer the plain verb; drop Latinate
alternatives"*. Drop anything true only of that one skill. Merge rules
that say the same thing twice.

Then propose the edit, as a diff like any other:

- **In the framework repository**, write them into the delimited region
  at the end of this skill's `SKILL.md`. The maintainer of this
  framework is setting framework authoring conventions, and they land
  through the normal reviewed change like any other. Use bullets and no
  headings inside that region — a new heading there would move the
  skill's `surface_hash` and tell every adopter their configuration went
  stale over a wording preference.
- **In an adopter repository**, write them into
  `.apache-magpie-local/optimize-skill.md`, which this skill already
  reads on every run. A framework file would be overwritten on the next
  upgrade, and one adopter's house style is not another's.

Show the diff and let the maintainer confirm it, the same as any other
pass. Rules learned in one session are a proposal, not a decision.
