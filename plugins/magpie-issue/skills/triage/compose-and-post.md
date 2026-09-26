<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Compose, confirm, and post the proposal comment

Companion to [`SKILL.md`](SKILL.md). Body of Steps 4-6: composing the
proposal comment (comment shape, `@`-mention routing, and the coherence
self-check), confirming the post list with the user, and posting
sequentially via the tracker's write API.

For each classified issue, compose **exactly one** comment. The
shape is:

```markdown
**Triage proposal**

<One-paragraph technical summary in the triager's own words —
not a copy of the report body. Cites the specific code location
and the documented behaviour, links to comparable issues when
applicable.>

**Proposed disposition: <CLASS>.**

<Rationale sentence — what evidence supports the class.>

<Fix-shape or action sentence — for BUG / FEATURE-REQUEST: what
would the fix look like, in one or two sentences. For NEEDS-INFO:
the specific information needed. For INVALID / DUPLICATE /
ALREADY-FIXED: the *why not* or *where it lives now* framing.>

<Optional Action items: numbered list when there's more than one
concrete thing the team needs to decide; otherwise a single
sentence.>

@<handle-1> @<handle-2> — <a specific question the @-mentioned
people are best placed to answer>?
```

## `@`-mention routing

The skill picks **2–3 maintainer handles** per comment from the
roster cached in Step 0. The picking heuristic:

1. **Component-based** — issues labelled `component:scheduler`
   (or analogous) route to the maintainers of that component per
   [`<project-config>/release-trains.md`](../../../../projects/_template/release-trains.md).
2. **Topic-specific override** — if the issue is a variant of a
   recently-discussed issue, also tag the handle of whoever owned
   that prior discussion.
3. **Never tag the triager themselves** — drop their handle from
   the routing set before composition.
4. **Never tag the entire roster** — 12+ handles trains the team
   to ignore the pings. Cap at 3 per comment.

If the roster file is missing or has no roster for the relevant
component, the skill stops and asks the user to populate it rather
than guess.

### Coherence self-check before presenting the draft

Re-read the draft once with the report's text beside it. Verify:

- the draft accurately characterises **this** issue (not a sibling
  the triager happened to be thinking about);
- every cited code location, commit SHA, or sibling-issue link
  was verified in Step 2 — no hallucinated identifiers;
- the link-form self-check passes — every issue reference uses
  the project's `issue_url_template`;
- the canned-response name (if `NEEDS-INFO`) matches a real
  heading in
  [`<project-config>/canned-responses.md`](../../../../projects/_template/canned-responses.md);
- the linked sibling issue (if `DUPLICATE`) is open or closed
  appropriately for the proposed merge direction;
- the fixing commit (if `ALREADY-FIXED`) actually touches the
  cited code path — verified by `git log` not pattern-matched
  from the issue body.

A draft that fails the self-check is rewritten before being
shown to the user, not surfaced as a half-baked proposal.

Present the full list of proposals as numbered items, grouped by
class. Accept any of:

- `all` — post every proposal as drafted.
- `1,3,5` — post only the listed items.
- `NN:edit <freeform>` — apply a tweak to item NN; re-draft and
  re-confirm.
- `NN:downgrade <CLASS>` / `NN:upgrade <CLASS>` — change the
  classification for item NN; re-draft and re-confirm.
- `NN:skip` — drop item NN from the post list.
- `none` / `cancel` — bail entirely.

Never assume confirmation. If the user replies ambiguously, ask
again on the specific items in question.

For each confirmed proposal, post one comment via the tracker's
write API:

- **JIRA**: REST POST to
  `<issue-tracker>/rest/api/2/issue/<KEY>/comment` with the body
  in the request payload, or `<jira-cli> issue comment <KEY> --body-file <tmp>`.
- **GitHub Issues**: `gh issue comment <N> --repo <upstream> --body-file <tmp>`.
- **Other trackers**: project-specific; the recipe lives in
  [`<project-config>/issue-tracker-config.md`](../../../../projects/_template/issue-tracker-config.md).

**Use the file-via-Write-tool pattern for the body** — direct CLI
arguments are vulnerable to shell expansion of `$(...)` when the
body contains user-supplied text (the issue body crossed a trust
boundary at import time). Write the body to `/tmp/triage-<KEY>.md`
via the Write tool, then pass with `--body-file` or as a request
payload.

**Before posting, scrub the body for bare-name mentions** of
maintainers per the rule in
[`AGENTS.md`](../../../../AGENTS.md#mentioning-project-maintainers-and-security-team-members).
Step 4 already uses `@`-handles, but the technical-summary
paragraph may have absorbed a bare name from the report body —
replace it with the corresponding `@`-handle so the tracker
actually notifies the person.

Apply **sequentially**, not in parallel — even though
classification ran in parallel via subagents (in bulk mode), the
apply phase is one-at-a-time so partial failures stay legible and
the user can interrupt cleanly.

After each post succeeds, capture the returned comment URL for
the recap in Step 7.

If any post call fails, stop and report the failure — do not
retry blindly. The likely cause is a transient rate-limit or
expired auth; the user retries the remaining items with the
`NN,MM,...` selector.
