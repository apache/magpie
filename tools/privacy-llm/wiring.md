<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Skill-wiring pattern — applying the privacy-LLM contract](#skill-wiring-pattern--applying-the-privacy-llm-contract)
  - [The protocol at a glance](#the-protocol-at-a-glance)
  - [Step 0 — pre-flight](#step-0--pre-flight)
  - [Redact-after-fetch protocol](#redact-after-fetch-protocol)
  - [Reveal-before-send protocol](#reveal-before-send-protocol)
  - [Configuration knobs the adopter can tune](#configuration-knobs-the-adopter-can-tune)
  - [Edge cases and failure modes](#edge-cases-and-failure-modes)
  - [Skills that follow this pattern](#skills-that-follow-this-pattern)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Skill-wiring pattern — applying the privacy-LLM contract

This file is the **canonical pattern** every `<security-list>`-
or `<private-list>`-touching skill follows when it reads private
mail content. Skill `SKILL.md` files link here from their pre-
flight section rather than copying the protocol — keeping the
pattern in one place avoids drift across skills.

If you are writing a new skill that may read private mail
content, add a Step 0 bullet that points at this file, then add
the two work steps documented below (redact-after-fetch and
reveal-before-send). The redactor itself is documented in
[`pii.md`](pii.md); the approved-LLM gate is in
[`models.md`](models.md); the adopter's per-project config lives
at `<project-config>/privacy-llm.md`
([`projects/_template/privacy-llm.md`](../../projects/_template/privacy-llm.md)
is the starting point).

## The protocol at a glance

```text
Step 0 (pre-flight)        check the privacy-llm config exists
                           load <project-config>/privacy-llm.md
                           verify the active LLM stack is approved
                                  (when reading <private-list>)

Step N (after fetch)       resolve collaborators (gh api repos/<tracker>/collaborators)
                           identify third-party PII in body
                           filter out: the reporter + every collaborator
                           pii-redact --field <type>:<value> ... (the filtered set)
                           use the redacted body for ALL subsequent processing

Step M (before send)       (only when emitting a body that mentions a
                            redacted third-party identifier)
                           pii-reveal on the rendered draft / comment text
                           send the revealed body
```

Three rules govern the whole protocol:

1. **The skill does the filtering.** The redactor is a generic
   value→identifier swap; it does not know who the reporter is
   or who is a collaborator. The skill identifies third-party
   PII candidates in the body, filters out the reporter and
   collaborators, and only passes the *should-be-redacted* set
   to `pii-redact`.
2. **The body is redacted exactly once, immediately after fetch.**
   No "redact later when convenient" — the window between the
   `mcp__claude_ai_Gmail__get_thread` (or PonyMail equivalent)
   tool call and the redact call should be a single tool
   invocation wide. After redaction, the redacted body is what
   flows through the rest of the skill.
3. **Reveal runs only at the outbound boundary.** When the skill
   is composing a draft / status comment / outbound text that
   carries one of *its own* redacted identifiers AND needs the
   real value at the destination, `pii-reveal` runs once on the
   rendered text right before the send tool is called.

## Step 0 — pre-flight

Add to the skill's existing Step 0 (pre-flight check) section:

```markdown
- **Privacy-LLM contract.** Run the gate-check via the
  `privacy-llm-check` console script — it parses
  `<project-config>/privacy-llm.md`, verifies every entry in the
  *Currently configured LLM stack* is approved per
  [`tools/privacy-llm/models.md`](../../tools/privacy-llm/models.md#the-pre-flight-check),
  and exits non-zero on any unapproved entry.

      uv run --project <framework>/tools/privacy-llm/checker \
        privacy-llm-check --reads-private-list

  Pass `--reads-private-list` when the skill may read
  `<private-list>` content; omit it for `<security-list>`-only
  flows (the check itself is the same — the flag only controls
  the printed banner). The skill also confirms:

  - `~/.config/apache-magpie/` is writable (the redactor's
    mapping file lives there). If not, prompt the user to
    create it.
  - The collaborator-source repository (default: the
    `<tracker>` declared in
    `<project-config>/project.md`; override per
    `<project-config>/privacy-llm.md → Collaborator
    source`) is reachable via `gh api`.
```

The pre-flight is read-only — no PII has been fetched yet. A
failed pre-flight (gate-check exit non-zero, or any of the other
checks above) does not write to the mapping file or the
tracker; the skill stops and surfaces the failure to the user.

## Redact-after-fetch protocol

After every `mcp__claude_ai_Gmail__get_thread` (or
`mcp__ponymail__get_thread` / `mcp__ponymail__get_email`) on
`<security-list>` mail, run this sequence before any further
processing of the body:

1. **Resolve collaborators.** Fetch the collaborator login set
   for the configured collaborator source:

   ```bash
   gh api repos/<tracker>/collaborators --jq '.[].login'
   ```

   The result is a list of GitHub logins. Skills SHOULD also
   resolve `name` and `email` per login when those are
   available (`gh api repos/<tracker>/collaborators --jq '.[]
   | {login, name: .name, email: .email}'`) — that lets the
   skill match real-name and email mentions in the body
   against collaborators, not just GitHub-handle mentions.

2. **Identify third-party PII candidates in the body.** The
   skill scans the thread body, signature lines, CVE credit
   fields, and HackerOne / GHSA fields for natural-person
   names, emails, phones, IPs, and personal handles. The
   reporter's own values (parsed from the `From:` header) are
   identified separately so they can be excluded.

3. **Filter the candidate set.** Drop any candidate that is:

   - The reporter's own name / email / phone / handle from
     the `From:` header.
   - A collaborator's login, name, or email from the set
     resolved in step 1.

   What remains is the **should-be-redacted set** —
   third-party PII that is neither the reporter nor a
   collaborator.

4. **Call the redactor.** For each remaining candidate, pass a
   `--field <type>:<value>` argument to `pii-redact`. The
   `<type>` codes are `name`, `email`, `phone`, `ip`,
   `handle`, `address` — see
   [`pii.md`](pii.md#what-counts-as-pii) for which fields
   trigger which type.

   ```bash
   echo "$BODY" | uv run --project <framework>/tools/privacy-llm/redactor \
     pii-redact \
     --field name:"Other Researcher" \
     --field email:"other@example.com" \
     --field handle:"otherresearcher-personal"
   ```

   The redactor returns the body with the matched values
   replaced by `<TYPE>-<hex>` identifiers. The mapping file at
   `~/.config/apache-magpie/pii-mapping.json` is updated in
   place.

5. **Use the redacted body for all subsequent processing.**
   Tracker-issue body, status comments, candidate analysis,
   prior-art lookup — every downstream step operates on the
   redacted text. The original (un-redacted) body is dropped
   from the agent's working set; if it is needed again, the
   skill re-fetches.

## Reveal-before-send protocol

When the skill is about to emit a body that:

- carries a redacted third-party identifier, AND
- is destined for a surface that needs the real value (a draft
  reply to the reporter, a CVE credit line, a public advisory
  with the third-party's accepted credit),

run `pii-reveal` on the rendered text once, right before the
send tool is called:

```bash
echo "$DRAFT" | uv run --project <framework>/tools/privacy-llm/redactor pii-reveal
```

`pii-reveal` reads the local mapping and substitutes any
identifier it knows about. Identifiers it does not recognise are
passed through unchanged — no risk of collision-corruption.

Reveal does **not** run on:

- Status comments / sync messages where the redacted form is
  fine (the security team can read identifiers).
- Public surfaces where the third party has *not* consented to
  being credited — the framework's
  [Confidentiality of the tracker repository](../../AGENTS.md#confidentiality-of-the-tracker-repository)
  rules apply on top.

## Configuration knobs the adopter can tune

The adopter's per-project `<project-config>/privacy-llm.md`
controls these knobs (see
[`projects/_template/privacy-llm.md`](../../projects/_template/privacy-llm.md)
for the template):

| Knob | Default | Notes |
|---|---|---|
| **Private mailing lists** | `<private-list>` only | Adding a list here gates skills that read it on the approved-LLM check (see [`models.md`](models.md)). |
| **Approved LLM stack** | Claude Code only | Add other approved entries with the data-residency-contract line per [`models.md`](models.md#the-opt-in-entries--adopter-declares-explicitly). |
| **Collaborator source** | `<tracker>` (from `<project-config>/project.md`) | Override here if collaborators are tracked in a different repo (e.g. a parent org repo, or a separate roster repo). |
| **Collaborator exemption** | enabled (collaborators NOT redacted) | Disable here to redact every non-reporter individual including collaborators — stricter posture; use when the project's PMC has decided collaborator names should never enter LLMs even when public. |
| **Redaction field types** | all six (`name`, `email`, `phone`, `ip`, `handle`, `address`) | Disable individual types here if a project has decided the sensitivity tradeoff differs (rare; the framework default is to redact all six). |

The redactor itself reads no config file — it just does what
the caller passes via `--field`. The skill applies the per-
project knobs at filter time (step 3 above):

- **Disabled type**: the skill does not generate `--field`
  args of that type, even when matching values are found.
- **Disabled collaborator exemption**: the skill skips step 3's
  collaborator filter, so collaborator names get redacted too.
- **Different collaborator source**: the skill uses the
  configured repo in step 1 instead of `<tracker>`.

## Edge cases and failure modes

| Condition | Handling |
|---|---|
| `gh api` collaborator lookup fails (network, auth, rate-limit) | Skill stops with an error. Do **not** fall back to "redact everyone including collaborators" silently — that produces a body where collaborator names are now identifiers, which downstream skills would not expect. The user retries the skill once the lookup works. |
| The reporter is *also* a collaborator | The reporter's own values are excluded from redaction (step 3, first bullet). The collaborator filter does not apply to them — there is no special second-pass. |
| The body contains a self-reference (`I am X`) where X is a collaborator | X is filtered out as a collaborator regardless. (Also: probably not a thing — collaborators rarely send security@ mail about themselves.) |
| The mapping file at `~/.config/apache-magpie/pii-mapping.json` is corrupt | `pii-redact` returns exit code 2 with the parse error on stderr. The skill stops; the user investigates the mapping file before re-running. |
| `pii-reveal` encounters identifiers not in the local map | They pass through unchanged. The skill should still complete its outbound, with the unknown identifiers preserved in the draft text. (This is the cross-machine case: a colleague redacted, you are revealing.) |

## Skills that follow this pattern

The skill files below all wire this protocol in their Step 0
pre-flight + a redact-after-fetch step + (where applicable) a
reveal-before-send step. Adding a new Gmail- or PonyMail-touching
skill that handles `<security-list>` content? Add it here and
add the corresponding wiring to the new `SKILL.md`.

| Skill | Reads | Drafts |
|---|---|---|
| [`security-issue-import`](../../skills/security-issue-import/SKILL.md) | `<security-list>` Gmail threads | reporter receipt-of-confirmation reply |
| [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) | `<security-list>` Gmail threads | reporter status updates |
| [`security-issue-invalidate`](../../skills/security-issue-invalidate/SKILL.md) | `<security-list>` Gmail threads | reporter invalidation reply |
| [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md) | tracker + Vulnogram | n/a (Vulnogram is OAuth-gated, body is in tracker which is already redacted) |
| [`security-issue-import-from-md`](../../skills/security-issue-import-from-md/SKILL.md) | adopter-supplied markdown file | n/a |
| [`security-issue-import-from-pr`](../../skills/security-issue-import-from-pr/SKILL.md) | public PR | n/a (no `<security-list>` content) |
| [`committer-onboarding`](../../skills/committer-onboarding/SKILL.md) | `<private-list>` vote thread (pasted by nominator) | congratulations email, secretary request, welcome announcement |
| [`security-issue-fix`](../../skills/security-issue-fix/SKILL.md) | tracker (already redacted) | n/a (PR is public, must not include any PII) |
| [`security-issue-deduplicate`](../../skills/security-issue-deduplicate/SKILL.md) | two trackers (already redacted) | n/a |
