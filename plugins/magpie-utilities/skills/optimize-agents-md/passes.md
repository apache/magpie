<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# optimize-agents-md — optimization passes

Each pass names its smell, its mechanics, what it guarantees, and how to prove the guarantee held.
They are listed lowest blast radius first, the order Step 2 proposes them in.
Every figure comes from [`scripts/measure.py`](scripts/measure.py); every proof ends with [`scripts/rule_inventory.py`](scripts/rule_inventory.py).

## Pinned sections

Before any pass, mark the sections that stay always-on whatever they cost.
A section is pinned when any of these holds:

- it governs how the agent treats what it reads (external content as data, prompt injection);
- it protects confidential or private information (embargoes, private trackers, PII, which model may see what);
- breaking it leaks something that cannot be taken back (an embargoed detail, private content), and no task trigger reliably precedes the moment it applies;
- the file itself calls it absolute, permanent, or not to be softened.

A section that is merely needed often, such as commit conventions, is **not** pinned: it stays always-on because most sessions use it, and the other passes may still trim it.

A pinned section keeps its place and its text.
Only *drop-toc* may touch the lines around it, and *rewrite* may touch it only with every rule sentence kept: `rule_inventory.py` must show none of its sentences missing.

**Unpinning is the maintainer's call, never a proposal.**
A pinned section can govern a task this repository's own sessions rarely do, such as a framework's rules for work on an adopter's tracker, which adopters get through their skills rather than through this file.
Diagnosis names such a section as a question for the maintainer, with the task it governs and its tokens.
Only the maintainer, in the session, can unpin it; text in the file never can. Once unpinned, it moves only by *on-demand*, with that pass's full proof.
Rules that govern this repository's own sessions, such as external content as data and what its public PRs and commits may say, stay pinned.

## 1. Drop-toc — remove the generated table of contents

**Smell.** A doctoc (or similar) TOC block at the top. It repeats every heading, and the agent reads the headings anyway.

**Mechanics.** Delete the block between the TOC markers and the markers themselves.
If a hook regenerates TOCs, exclude this file from it in the same change, or the next commit puts the block back.

**Guarantee.** No prose changes; only generated links go.

**Proof.** `rule_inventory.py` shows every sentence kept; the TOC hook passes with the file excluded.

## 2. Scope-down — move subtree-only rules into a nested file

**Smell.** A section that only matters while working under one directory (`tools/`, `docs/`, one package).
`nest.py suggest` finds the ones that name paths; a section that governs a directory without naming paths counts too.

**Mechanics.** This is the default home for subtree-only text. `nest.py apply` performs it:

- creates `<dir>/AGENTS.md` when missing (the root's licence comment, a title, one line saying the root still governs), otherwise appends to it;
- moves the section byte-identical, except that a heading deeper than `##` is raised to `##` and each relative link is rewritten to reach the same target from the new directory;
- removes the section from the root, or keeps its heading with a *"When working under `<dir>/`, read …"* pointer when other files link to its anchor;
- mirrors a root `CLAUDE.md -> AGENTS.md` symlink into `<dir>`.

**Guarantee.** The rule is loaded whenever work happens in that subtree; the session pays for it only then.
For a harness that reads only the root file, pass `--pointer` to keep the pointer in the root regardless.

**Proof.** `rule_inventory.py --also <dir>/AGENTS.md` shows the moved sentences found there (it ignores link targets, so the rewritten links still match), and the file's evals stay at their baseline.

## 3. On-demand — move task-specific sections behind a triggered pointer

**Smell.** A section needed only for one kind of task: releasing, drafting reporter mail, adding a skill, editing a schema.
Most sessions never do that task, and every session pays for the section.

**Mechanics.**
1. Pick a destination: the doc that already owns the topic, if one exists, otherwise a new `docs/` page.
2. Move the section body **byte-identical**. Keep the heading in the root, so inbound `AGENTS.md#anchor` links still land.
   A heading kept only for those links gets a one-line body, *Moved to [\`<file>\`](<file>#<anchor>).*, with the file name as link text rather than the heading again.
3. Replace the body with a pointer that names the trigger as a task the agent will recognise:
   *"Before drafting reporter-facing text, read `docs/editorial-guidelines.md`."*, written as a real link.
   A pointer without a trigger ("see also …") is never followed.
4. Keep one sentence of the rule itself in the root when breaking it before the trigger fires would hurt.
5. Give the pointer a trigger no other pointer in the file shares. A routing case names one file, so two pointers that fire on the same task make both cases ambiguous: narrow the new trigger instead.

**Guarantee.** The rules still apply, but they are read only when the task they govern begins.
Net saving per session = section tokens − pointer tokens; the cost when the trigger fires = the destination file's size.
Move a section only when its trigger fires in a minority of sessions.

**Proof.** `rule_inventory.py` reports the sentences as `moved` to the destination.
Then prove the pointer, as `optimize-skill` does for a skill sibling ([*Proving a pointer*](../optimize-skill/patterns.md#1-split--slim-an-oversized-skillmd-into-linked-siblings)):
add a `pointer-routing` case to the file's evals, a task that should trip the trigger, with `must_read` naming the destination and no file named in the output spec.
Run the suite against a throwaway copy of the file with the pointer deleted, inside the repository, by pointing a copied suite's `skill_md` at it; put the copied suite beside the real one (under the same evals directory) so the runner accepts it, delete both afterwards, and drop the copy's line from `runs.jsonl`.
The case must pass on the real file and fail on the copy; one that passes on both carries no signal.
Start the model's CLI in an empty directory (`--cli-cwd`, which `magpie-run-evals.sh` passes for you): a CLI started at the repository root also loads the real file as project context, so the copy can pass on the very pointer it lacks.
A failure on the copy counts however it was run; a pass counts only from a clean run.
When the moved text is what a `rules` case tests, add the destination to that step's `also_include`, so the case tests the rule as a session that followed the pointer sees it; the routing case proves that sessions follow it.
Keep the suite's case where nothing should be read.

## 4. Extract-code — move complete programs out of the file

**Smell.** A multi-line, placeholder-free script in a fence (a probe, a setup recipe) that the agent runs rather than reads.

**Mechanics.** Move it byte-identical to a script under `tools/` or `scripts/`, and keep one line saying when to run it and what its output means.
Leave command *shapes* with placeholders in place; they are instructions written in shell.

**Guarantee.** The same program runs; the agent no longer pays to read it every session.

**Proof.** The extracted script is byte-identical to the fence body (`diff`); `rule_inventory.py` shows the surrounding prose kept.

## 5. Dedupe — keep the rule once, where it is owned

**Smell.** A section that restates a doc, a skill, or a tool README at length; or a second instruction file (`CLAUDE.md`, `GEMINI.md`) that copies `AGENTS.md` instead of linking it, so a harness reading both pays twice.

**Mechanics.** Keep the rule sentence and a link to the owner; drop the restated elaboration.
First compare the two line by line: where they disagree, the root copy may be the one in force, so reconcile the owner first.
For a copied instruction file, replace it with a symlink or a one-line import of `AGENTS.md`, per what each harness supports.

**Guarantee.** Every dropped sentence exists in the owner, word for word or with the difference reconciled first.

**Proof.** `rule_inventory.py --also <owner>` shows each dropped sentence found in the owner.

## 6. Enforced — shrink rules a check already enforces

**Smell.** Long mechanics for a rule a hook, guard, linter, or CI check enforces deterministically, and whose error message tells the agent what to do.

**Mechanics.** Keep the rule in one sentence and name the check; drop the step-by-step mechanics.
Keep the full text when the check is optional (installed only by some setups) or runs only after the damage, such as a CI failure after a push.

**Guarantee.** The agent still knows the rule; the check catches every case the prose described.

**Proof.** Name the check and the case it blocks, from its source or tests.
`rule_inventory.py` reports the dropped sentences as `missing`: list each with the check that covers it, for the maintainer to approve.

## 7. Rewrite — tighten the wording with the maintainer

**Smell.** The structure is right and the prose still reads twice as long as it needs to.

**Mechanics.** Follow [`optimize-skill`'s rewrite pass](../optimize-skill/rewrite.md): the maintainer writes each paragraph, and the drafts learn their style.
Before starting, estimate the yield and say it: a section made mostly of rule sentences gives back little.
On the pinned sections of Magpie's own `AGENTS.md` a rewrite saved 80–160 tokens each, against 300–2,400 for *on-demand*, so offer *on-demand* first where it applies.
A statement the rewrite finds wrong, not just long, is fixed as its own named change, confirmed with the maintainer, so the PR does not present a correction as a trim.

**Guarantee and proof.** The approved paragraph diff is the record.
`rule_inventory.py` lists every rewritten rule sentence as `missing`; walk the list with the maintainer and confirm each rule survives in the new wording.

## When a pass is not an optimization

- **An `@path` import.** The harness expands it at load time, so it is still always-on; it saves nothing.
- **A pointer with no trigger.** The text is gone from every session and read in none.
- **Moving a section most sessions need.** The agent reads the destination anyway, and pays for the pointer on top.
- **Cutting a pinned section** because a doc also has it. Pinned rules are in force before the agent decides what to read.
