<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Golden rule details

Companion to [`SKILL.md`](SKILL.md). Full body text of the Golden rules; SKILL.md keeps each rule's title with a pointer here.

**Golden rule 1 — read-only on tracker state.** This skill posts
discussion comments and nothing else. No workflow transitions, no
assignments, no label mutations, no body edits, no project-board
column moves, no field changes. The skill's output is *text on the
tracker that invites reaction*; the team's reply drives state change, applied
later by sibling skills.

**Golden rule 2 — every comment is a draft until the user
confirms.** Triage proposals are public(-ish) comments on
`<issue-tracker>`, attributed to the maintainer who invoked the
skill. Per the "draft before send" rule in
[`AGENTS.md`](../../../../AGENTS.md), every comment is drafted, shown to
the user, and posted only after explicit confirmation. The fact
that the user invoked the skill is **not** blanket authorisation —
the text of each comment is reviewed individually.

**Golden rule 3 — six disposition classes, no more.** The
classification is a proposal, not a verdict; the team's reply may
escalate or de-escalate. The skill always proposes exactly one
class per issue — never two — because a two-class proposal stalls
the discussion rather than starting it.

| Class | When to propose | Sibling skill / action |
|---|---|---|
| `BUG` | Confirmed actionable bug; reproduces or has compelling evidence | [`issue-fix-workflow`](../fix-workflow/SKILL.md) |
| `FEATURE-REQUEST` | Valid improvement or new-feature request; not a bug | Re-type as Improvement; route to project's roadmap |
| `NEEDS-INFO` | Missing repro steps, environment, version, or other actionable detail | Request info from reporter |
| `DUPLICATE` | Substantive overlap with an existing tracker issue (open or closed) | Link to canonical issue |
| `INVALID` | By-design, won't-fix per project policy, out-of-scope, or environment-specific | Close with rationale |
| `ALREADY-FIXED` | A commit on `<default-branch>` covers the report; the issue just needs closing | Close referencing the commit |

**Golden rule 4 — never auto-escalate from a comment reply to a
mutation.** A reply on the tracker like *"agreed, close it"* is
**not** authorisation for this skill to close the issue or
transition state. The user types the next slash command explicitly;
this skill's job ends at "comment posted".

**Golden rule 6 — flag, do not assert, contributor-side facts AI
cannot verify.** If the proposal touches on first-time-contributor
status, licence agreement acceptance, or a reporter's prior contribution
history, the skill *flags* the fact for the maintainer to check —
it does not *assert* the fact. AI tooling has no authoritative
view of CLA state or contributor history.

**Golden rule 7 — grounded claims only.** Every non-trivial
technical claim in the proposal body must be grounded in something
run or searched (command output, code reference, prior tracker
link) — not speculation. Hallucinated API names, fabricated commit
SHAs, and plausible-sounding-but-unverified identifiers are the
most common failure mode for AI-drafted triage; the coherence
self-check in Step 4 enforces this.
