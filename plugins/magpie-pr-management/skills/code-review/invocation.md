<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## How to invoke — examples

The slash command is `pr-management-code-review`. A few worked
examples a maintainer can paste:

| Goal | Invocation |
|---|---|
| Walk through everything in **"my reviews"**, newest first | `pr-management-code-review` |
| Review a single PR (the most common ad-hoc trigger) | `pr-management-code-review pr:65981` |
| Just the PRs where I'm a CODEOWNER, ignore the rest | `pr-management-code-review codeowner-only` |
| PRs that explicitly `@`-mention me, skip the noise | `pr-management-code-review mentioned-only` |
| Re-look at the PRs I already reviewed (follow-ups after author push) | `pr-management-code-review reviewed-before-only` |
| My-reviews **but** drop touching-mine (too noisy this morning) | `pr-management-code-review no-touching-mine` |
| My-reviews limited to scheduler-area, max 5 | `pr-management-code-review area:scheduler max:5` |
| My-reviews scoped to non-collaborator authors (extra-careful pass) | `pr-management-code-review collab:false` |
| The team queue (PRs where `<upstream>-<team-name>` is requested) | `pr-management-code-review team:project-team-name` |
| The wider curated queue triage already promoted | `pr-management-code-review ready` |
| Stay body-only this session (no inline picker) | `pr-management-code-review inline:off` |
| Dry-run the queue — draft everything, post nothing | `pr-management-code-review dry-run` |
| Same, against a different repo | `pr-management-code-review dry-run repo:<upstream>-site` |
| Have other models read each PR adversarially, run by the agent | `pr-management-code-review with-reviewers:codex,copilot` |
| Pair with an adversarial reviewer for a second read on each PR | `pr-management-code-review with-reviewer:/codex-plugin:adversarial-review` |
| Skip background analysis subagents (tiny queue, prefetch is wasted) | `pr-management-code-review max:1 no-prefetch` |

Selectors compose freely. Most flags carry through cleanly:
`area:scheduler reviewed-before-only since:7d` is "PRs in
the scheduler area that I reviewed in the last 7 days."

When in doubt, run with no flags first — the default surfaces
everything you'd reasonably be expected to look at.

---

## Parameters the user may pass

| Selector / flag | Effect |
|---|---|
| `pr:<N>` | review only PR `<N>` |
| `area:<LBL>` | restrict to PRs carrying `area:<LBL>` (wildcards supported) |
| `collab:true|false` | restrict to PRs whose author is / isn't a collaborator |
| `team:<NAME>` | restrict to PRs requesting review from a team `<viewer>` is on |
| `ready` | source from the `ready for maintainer review` label instead of the default union |
| `requested-only` / `mine-only` / `codeowner-only` / `mentioned-only` / `reviewed-before-only` | use only one half of the my-reviews union |
| `no-touching-mine` / `no-codeowner` / `no-mentioned` / `no-reviewed-before` | drop just one half; keep the rest |
| `since:<window>` | tune the touching-mine main-branch recency window (default `30d`) |
| `with-reviewers:<list>` | run these model CLIs as adversarial reviewers through the adversarial-review tool |
| `with-reviewer:<command>` | name the slash command to propose for second-read coverage |
| `repo:<owner>/<name>` | override the target repository |
| `max:<N>` | stop after `<N>` PRs reviewed |
| `dry-run` | draft but never post |
| `no-adversarial` | skip the optional second-reviewer step |
| `inline:off` (alias `body-only`) | suppress the inline-comments picker; post body-only reviews this session |
| `lookahead:<N>` | size of the background-analysis lookahead window (default `3`) |
| `no-prefetch` | disable background analysis subagents for this session |

When in doubt about the selector, ask the maintainer *before*
fetching — a one-line clarification is cheaper than a 30-PR
list-then-throw-away.
