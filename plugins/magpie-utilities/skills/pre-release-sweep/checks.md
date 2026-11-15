<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# What each area looks for

Each area names the question, where to look, and the PR that set the pattern; read that PR's body for a worked example of the evidence a finding needs.

## A — Specs behind `main`

`tools/spec-loop/.last-sync` names the last commit the specs describe.
List the commits since, and for each say which spec it changes or that it has none (a version bump, an actions bump, a PR that updated its own spec).
Update the specs, bump `.last-sync`, and run `spec-validate`.
Pattern: #2088. This is the last PR of the sweep.

## B — Docs that describe a repository that no longer exists

Read `AGENTS.md`, `PRINCIPLES.md`, `CONTRIBUTING.md` and the authoring skills against the tree: where skills live, how they are linked, what the scaffold creates, which keys the validator requires, which branch is the base.
Also: a skill sibling no step links to; a sibling that repeats `SKILL.md`; a file named `SKILL.md` that is not a skill; a `SKILL.md` at or over the line cap.
Pattern: #2090.

## C — Principles against practice

For each section of `PRINCIPLES.md`, find what the code and skills actually do.
A principle the framework no longer follows is either rewritten (with the maintainer) or the practice is fixed; never both silently.
Check every link to a principle anchor still resolves after a renamed heading.
Pattern: #2089.

## D — Commands and paths that do not work

Every command a doc or skill tells the agent or the user to run: compare it with the CLI's `--help` (subcommands, flag names, choice values, required arguments).
Every path: does it exist on each install method, in particular a marketplace install, where only what the plugins ship is materialised?
Every config key a doc says a file declares: does the template define it and does code read it?
Pattern: #2093.

## E — Referenced tools that are not shipped

Inventory every `<framework>/tools/<x>` reference and every runnable `tools/<x>` path in user-facing text, against what a marketplace install ships.
For each gap, ship the tool or say where it comes from instead.
Pattern: #2099.

## F — Placeholders

One placeholder, one spelling, one definition in the `AGENTS.md` placeholder table, backed by a template key; no concrete project value in a skill.
Pattern: #2096.

## G — One thing measured two ways

A number computed in two places (a token count, a skill count, a cost): find each definition and make one the source the others point to.
Pattern: #2098.

## H — RFCs and design docs describing a superseded model

An accepted RFC whose model has since changed gets a dated note pointing at what replaced it; its text is not rewritten.
Pattern: #2097.

## I — Optimization candidates

From Step 1's token table: skills over the always-on budget (`description` + `when_to_use` past 200 tokens) or the body budget (past 5,000), a rule stated in several places, a rule inlined in `SKILL.md` that only some runs need, script internals the model never needs to read.
Propose the [`optimize-skill`](../optimize-skill/SKILL.md) pass for each; a sweep PR applies passes that move text, and leaves a rewrite to its own session.
Patterns: #2091, #2092, #2094, #2100, #2101.

## J — Evals

A live run costs one model call per case, so choose what runs:

- **live**: every suite whose skill or fixtures changed in the release range, and every suite whose last journaled run (the newest line of its `runs.jsonl`) failed or errored;
- **offline only** (`runner --check`, no model call): every other suite, including those with no `runs.jsonl` at all — list these with their case counts and let the maintainer pick which to run live, never all of them by default.

Every live run is journaled to the suite's `runs.jsonl` by the wrapper; render the README tables (`uv run --project tools/skill-evals skill-eval-journal render tools/skill-evals/evals`) and commit the journals, with the PR whose change they test or as one "record eval runs" PR, so the next sweep knows what already passed.
Trace each failure to the wrong side: a fixture left behind by a skill change, a fixture inconsistent with itself, an expected value the skill's own rules contradict, or skill wording loose enough to be flaky (re-run the case several times).
Pattern: #2095.

## K — Closable issues

See [`issues.md`](issues.md).
Pattern: #2060.
