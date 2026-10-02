<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-triage — proposal composition

## Step 4 — Compose proposal comment

### `@`-mention routing

The skill picks **1-3 security-team handles** per comment from
the roster cached in Step 0. Priority order, applied
mechanically:

1. **PR-author of the analogous prior fix.** For each tracker,
   extract the code pointers (file paths, function names) from
   Step 2. For each pointer, run:

   ```bash
   gh search prs --repo <upstream> --json author,title,mergedAt,url \
     -- <pointer> security
   gh search prs --repo <upstream> --json author,title,mergedAt,url \
     -- <pointer> fix
   ```

   The most-recent matching PR's author is the **#1 pick** — they
   have the deepest current context. Cross-check against the
   security-team roster cached in Step 0; drop if not on the
   roster. If multiple PRs are recent, pick the one with the
   tightest title-match on the tracker's vulnerability class
   (e.g. "auth" / "deserialize" / "path traversal").

2. **Recent reviewer of the area.** For the same code pointer,
   find roster members who have reviewed recent PRs:

   ```bash
   gh pr list --repo <upstream> --search 'reviewed-by:<handle>' \
     --limit 100 --json files,reviews,mergedAt -- <pointer>
   ```

   Iterate the roster (cached in Step 0); the roster member with
   the most-recent review in the area is the **#2 pick**.

3. **Scope-default fallback.** Only if 1 and 2 yield nothing,
   fall back to the scope-based subset from
   [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md).
   Pick **1 person**, not 3 — a single targeted ping outperforms
   a roster sweep. The project may declare per-scope expertise
   hints under a "Security team area-of-expertise hints"
   subsection of `release-trains.md`; honour those when present
   but do not require them.

**Cache the routing decision per code area** within the run —
if 5 trackers all touch the same code area, the @-mention set is
identical for all 5 (computed once, re-used).

**Cap at 3 handles per comment**, prefer 2. The triager (cached
in Step 0 as `viewer_login`) is automatically excluded.

**Topic-specific override** (still applies on top of the above):
if a tracker is a variant of a recently-closed CVE, also tag
the `@`-handle of whoever owned that CVE's fix PR (the
topic-specific person has the richest context). Cap still
applies; if topic-specific puts you at the cap, drop the
scope-default fallback.

**Never tag the entire roster.** 12+ handles on every triage
comment trains the team to ignore the pings. If routing returns
more than 3 candidates, the cap forces a prioritised pick.

**Routing-failure fallback.** If the `gh search prs` queries
return nothing (new code area, no prior PRs), the skill stops
and surfaces *"no PR-history match for `<pointer>`; falling
back to scope-default — please confirm @-mentions before
posting"*. The user types the corrected handle(s) into the
proposal; the skill caches the decision for the rest of the
run so the same fallback doesn't recur on every tracker.

**Budget**: ≤ 2 `gh search prs` calls per unique code area
(across all trackers in a bulk run, post-caching). The cache
makes this trivially cheap even on large sweeps.

The roster source-of-truth is
[`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md);
the project-specific routing rules (which subset for which
scope) live in
[`<project-config>/project.md`](../../../../<project-config>/project.md).
If either file is missing or has no roster, the skill stops and
asks the user to populate it rather than guess.

### Coherence self-check before presenting the draft

Re-read the draft once with the report's text beside it. Verify:

- the draft accurately characterises **this** tracker (not the
  sibling vector you happened to be thinking about);
- the cited Security Model section actually contains the
  language quoted;
- the canned-response name (if `INFO-ONLY`) matches a real
  heading in
  [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md);
- the linked sibling tracker (if `PROBABLE-DUP`) is open or
  closed appropriately for the proposed merge direction;
- the link-form self-check passes — every `#NNN` is a clickable
  link, every CVE ID is linked per
  [`AGENTS.md`](../../../../AGENTS.md#linking-cves).

A draft that fails the self-check is rewritten before being
shown to the user, not surfaced as a half-baked proposal.
