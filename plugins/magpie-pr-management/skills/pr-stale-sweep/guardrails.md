<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Guardrails

## Disposition vocabulary

The skill uses **exactly two** disposition classes:

| Class | When to propose | Follow-up action |
|---|---|---|
| `REQUEST-UPDATE` | PR is dormant past the warn threshold but not yet past the close threshold; author has not recently responded | Post a nudge comment asking the author to confirm the PR is still in progress and they intend to address any feedback; no state change yet |
| `CLOSE-STALE` | PR is dormant past the close threshold **and** has already received a `REQUEST-UPDATE` nudge with no response, **or** is dormant past a hard-close threshold with no nudge needed | Post a pre-close notice and, on a second explicit confirmation, close the PR |

The two thresholds (`warn_days` and `close_days`) default to the values in
[`<project-config>/stale-sweep-config.md`](../../../../projects/_template/stale-sweep-config.md)
when that file exists, or to framework defaults (45 / 90 days) when it
does not. PR queues typically move faster than issue trackers, so the
framework defaults are tighter. The user may override either threshold
inline at invocation time.

---

**Golden rule 3 — two classes, no more.** The classification is either
`REQUEST-UPDATE` or `CLOSE-STALE`. No hybrid proposals in a single
comment.

**Golden rule 4 — never close without a posted nudge first (unless the
hard-close threshold applies).** A PR that has never received a
stale-sweep nudge must receive a `REQUEST-UPDATE` comment first, wait
the warn-to-close window, and only then be eligible for `CLOSE-STALE`.
The exception is the configurable `hard_close_days` threshold (default:
180 days) where a nudge is skipped for exceptionally dormant PRs.

**Golden rule 5 — never sweep maintainer-court PRs.** A PR where the
author's most recent activity includes an unanswered question directed
at a maintainer or the committers team is in the **maintainers' court**
— the next move is a maintainer responding, not anything the author
owes. Skip such PRs entirely and surface them in the recap so the
maintainer knows to respond.

**Golden rule 6 — never sweep `ready for maintainer review` PRs.** A PR
carrying the `ready for maintainer review` label (or equivalent
configured in
[`<project-config>/pr-management-config.md`](../../../../projects/_template/pr-management-config.md))
is waiting on maintainer action. Closing or nudging it for "inactivity"
punishes the contributor for maintainer silence. Skip such PRs
entirely.

**Golden rule 7 — every PR reference is clickable in the surface it
lands on.** Whenever this skill emits a reference to a PR — the
proposal body, the confirmation screen, the recap — it must be one
click away in whatever surface it lands on:

- **On markdown surfaces** (comment body posted to `<upstream>`,
  confirmation-screen preview): use the markdown link form per
  [`AGENTS.md` § *Linking tracker issues and PRs*](../../../../AGENTS.md#linking-tracker-issues-and-prs):
  `[<upstream>#NNN](https://github.com/<upstream>/pull/NNN)`.

- **On terminal surfaces** (the pre-post preview, the recap): wrap the
  visible short form in **OSC 8 hyperlink escape sequences**
  (`\e]8;;<URL>\e\\<short>\e]8;;\e\\`). Fall back to printing the bare
  URL on the same line after the number when OSC 8 is unsupported.

Bare `#NNN` with no link wrapper of any kind is never acceptable.

**Self-check before posting any comment**: grep the body for bare `#\d+`
tokens that aren't already inside a markdown link or an OSC 8 wrapper,
and convert any match.

**Golden rule 8 — screen for security signals.** Before proposing a
stale comment on any PR, check the PR title and body for signals that
the change may be a security fix (CVE references, mentions of "exploit",
"vulnerability", "injection", "auth bypass", coordinated-disclosure
language). If any signal is found, **skip that PR entirely** and surface
a warning to the user: the PR may need confidential handling rather than
a public stale comment.

**Golden rule 9 — never fabricate inactivity evidence.** The
classification is based on timestamps returned by the GitHub API
(`updated_at`, `pushed_at`, `last_comment_at`). Do not infer dormancy
from subjective reading of the PR body or diff. If timestamps are
unavailable, skip the PR and surface the gap.

---

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| Pool returns 0 candidates | Thresholds too high, PRs all carry the ready label, or queue is genuinely healthy | Surface and stop; suggest reducing `warn_days` or widening the filter |
| Pool exceeds 50 | Very large stale backlog | Stop; ask user to narrow with label filter or smaller threshold |
| Timestamp unavailable for a PR | GitHub API limitation for this PR type | Skip the PR, mark `SKIP-NO-TIMESTAMPS`, surface in recap |
| Second close confirmation refused | User changed their mind after seeing the comment posted | Leave the PR open; it already has the pre-close notice |
| Post call fails mid-loop | Transient rate-limit or auth expiry | Stop, surface the failed item, instruct the user to retry remaining items |

---
