<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently: a
couple of file checks, or one CLI call for a marketplace install.

**This block decides one thing: whether to stay silent.** Each step either
passes silently or sends you to `preflight-detail.md` — a file in this
skill's own directory, alongside this one — which carries that step's branch
handling, the rules constraining it, and the reasoning. The text here is
deliberately not enough to act on: **never act on a non-silent outcome
without reading that file first.** If it cannot be read, say so and continue
into the work the user asked for rather than improvising the branch.

1. **Is a lock present?** If `.apache-magpie.lock` exists, read its
   `method`.

2. **A snapshot method** (`svn-zip` / `git-tag` / `git-branch`) → compare
   with `.apache-magpie.local.lock`. Both present and agreeing on
   `ref` / `commit` → **silent**; continue. Anything unresolved → *detail,
   step 2*.

3. **`method: marketplace`** → the lock is the project's **floor**: a
   minimum version and a minimum plugin set, never a pin. Compare the
   machine against it.

   **First, check `url`.** If it is anything other than `apache/magpie`,
   run **nothing** → *detail, step 3*.

   Otherwise read the installed state — `claude plugin list --json`, or
   the running agent's equivalent. **An empty or unreadable result is
   unknown, never absent**: run nothing, propose nothing, say nothing,
   and carry on to step 4. Only a result the session actually read drives
   anything. Compare **as PEP 440, not as strings**, with no special
   handling for a `.devN` segment.

   - every floor plugin installed at or above `min_version` →
     **silent**; continue the skill;
   - anything else — a plugin absent, a plugin below `min_version`, or no
     such CLI to read → *detail, step 3*.

   **Never** remove a plugin, downgrade one, pin the marketplace to a tag,
   or touch a plugin absent from the floor. Being *ahead* of the floor is
   the normal case and is not a finding.

4. **Compare this skill's fingerprint against the reconciliation stamp.**
   Not install-method-specific, unlike step 3: it runs the same way for
   every `method`, and whether or not there is a lock. Skip it entirely —
   silent, no reads — when any of these holds:

   - none of `.apache-magpie.lock`, `.apache-magpie-local/` or
     `.apache-magpie-overrides/` exists: nothing has ever been configured,
     so there is nothing to reconcile;
   - step 3 ended in a state step 5 stops the run for — but **an *unknown*
     step 3 result is not one of those**, and this step runs normally
     after it;
   - this skill's own `surface_hash` is not in the context you were given:
     a check that cannot read its own input says nothing rather than
     guessing.

   Otherwise look this skill's frontmatter `name:` up in the lock's
   `reconciled.skills` map, already open from step 1 — no extra read.
   **Found and equal → silent**, and nothing else here needs a read.
   Anything else — differing, absent from the map, or no lock at all →
   *detail, step 4*.

5. **Unless step 3 passed silently or came back unknown, stop.** The
   session is still below the project's floor and has to be restarted
   before this command is re-run; *detail, step 5* has what to say. An
   unknown result carries no such action — nothing to say, nothing to
   restart for — so continue.

6. **No lock?** Then this is the marketplace install without adoption,
   or nothing at all. That is a supported end state, not a fault — what
   matters is whether *this skill's* configuration resolves.

7. **Resolve this skill's `requires_config:` frontmatter.** Each file,
   per the lookup chain: `.apache-magpie-local/<file>` (gitignored,
   personal) first, then `.apache-magpie-overrides/<file>` (committed).
   All present → **silent**, carry on.

   Any required file missing → **run `/magpie-setup config` for this
   skill now**, say that you are doing it and why, then continue into the
   work the user actually asked for. Two things it may not do: **fabricate
   a value** — anything it cannot derive from the repository is a question
   it asks or a `TODO` it leaves — and **continue past a value it needs
   but does not have**. Why running it unasked is safe, and why it needs
   no restart → *detail, step 7*.

8. **Never run `/magpie-setup adopt` unattended.** Adoption commits a
   recommendation for every contributor and is a maintainer's decision
   taken with the other maintainers. When configuration was just
   written locally, add **one line** saying the project can also adopt
   Magpie so contributors get this on clone, and name the command.
   Then drop it. Do not ask, do not offer to run it, and do not repeat
   it on later invocations.

9. **Note what needed confirming, and propose vetting the reads.** This
   step and step 10 are settled at the *end* of the run, not in pre-flight;
   they live here because this block is the one thing every skill carries.
   While you work, note each operation that stopped for a confirmation
   prompt. Say nothing when nothing prompted, or when everything that did
   was a write. Any that were **read-only** → *detail, step 9*. **Propose;
   never apply** — never edit the vetted-ops catalogue, the policy, or a
   permission rule.

10. **Suggest `/magpie-setup verify` when it is overdue.** Compare today
    against the **most recent** of `verified_at` and `verify_suggested_at`
    in `.apache-magpie-local/reconciled.json` (already read in step 4 if
    that step read it; read it now otherwise), and — when neither is
    present — against the stamp's `at:`. Within
    `setup.verify_interval_days` (project → organization → framework,
    default 14, `0` disables) → say nothing. Older → *detail, step 10*.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic.
