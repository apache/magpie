<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — GitHub repository security advisory reconciliation

> Extracted from [`SKILL.md`](SKILL.md) so subagents that only need this
> slice can load just this file. Loaded when a tracker is **GHSA-sourced**
> — i.e. its report arrived through GitHub's *"Report a vulnerability"*
> flow, which creates a **repository security advisory** (a `GHSA-…`
> draft) on `<upstream>`.

This subdoc covers reconciling that GitHub advisory **record** with the tracker, and the reporter-reply path when the operator has advisory API access.
It applies only when `<upstream>` is hosted on GitHub and the operator is a **collaborator** on the repository's security advisories.

The email relay to the hosting foundation's security team ([`tools/gmail/asf-relay.md`](../../../../tools/gmail/asf-relay.md)) is only the **fallback**:
the *repository security advisories REST API* exposes the advisory record for read + field-edit, so the sync reconciles it directly.
Only the reporter⟷maintainer **discussion thread** has no API.

---

## Access tiers — probe before acting

The GitHub *repository security advisories* API grants different operations at different tiers.
Probe the operator's tier once per run and record it in the observed-state bag:

| Operation | Endpoint | Tier required |
|---|---|---|
| List / read advisories (incl. `triage`/`draft`) | `GET /repos/<upstream>/security-advisories[/<GHSA>]` | **advisory collaborator** (or admin / security-manager) |
| Edit advisory **fields** (`cve_id`, `credits`, `severity`, `cwe_ids`, `vulnerabilities`) | `PATCH …/security-advisories/<GHSA>` | **advisory collaborator** |
| Manage **collaborators** (`collaborating_users`/`_teams`) | `PATCH …` with those fields | **admin / security-manager** |
| Change **state** / publish | `PATCH …` with `state`, or the publish call | **admin / security-manager** |
| Comment on the reporter discussion thread | *(none — `…/comments` → 404)* | **web UI only** |

Probe: the `gh api "/repos/<upstream>/security-advisories?per_page=100"` list call in the Step 1 add-on below
(a `200` with a list ⇒ at least collaborator read).
A collaborator-management `PATCH` returns
`403 "Cannot update advisory collaborators unless you have
administrative/security management rights"` when the operator is a plain collaborator:
treat that 403 as the definitive *"not admin"* signal, **do not retry**, and route the action to the admin hand-off below.

The common tier for a project committee member is **advisory collaborator**: read + field-edit, but **not** collaborator-management and **not** publish.
The sync does what that tier allows and *hands off* the rest —
never blind-fire a `state=published` PATCH: a success is a **permanent public advisory**.

---

## Step 1 add-on — fetch + reconcile (read; always runs)

Detect GHSA-sourced trackers by grepping the body / provenance for `GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}` ids scoped to `<upstream>`
(reuse the import skill's GHSA grep).
Take each id's advisory from one list call, which doubles as the access-tier probe above:

```bash
gh api "/repos/<upstream>/security-advisories?per_page=100"
```

Fetch an advisory individually (`gh api /repos/<upstream>/security-advisories/<GHSA>`) only when its id is not in that list — it is older than the first 100 — and record each one. Surface drift in the Step 2 proposal:

- **cve_id drift** — advisory `cve_id` ≠ the tracker's CVE (or empty).
- **field drift** — `credits` / `severity` / `cwe_ids` / `vulnerabilities` (affected ranges) differ between advisory and tracker.
  The tracker + CVE record is **authoritative**; the advisory is the mirror.
- **state drift** — advisory `state` vs the tracker's process step (e.g. tracker `announced` + CVE published while the advisory is still `triage`).
  Informational at the collaborator tier (state changes are an admin hand-off).

  **Check `published_at`, not just `state`.** An advisory can carry the CVE id, the right severity and complete content while `published_at` is still `null` — filled in but never published.

  **This is a reporter-facing gap, not bookkeeping.** On a GHSA-sourced tracker the reporter watches the advisory, not the mailing-list advisory or the CVE record,
  so a closeable tracker can look untouched since triage from the reporter's side. Two consequences:

  - **Do not let the tracker close silently past it.** When the tracker reaches its terminal step with the advisory still unpublished,
    surface it — closing is fine, going quiet is not.
  - **Fold the publish request into the existing admin hand-off relay** rather than opening a new thread,
    and pair it with the reporter reply so the reporter is not told *"it is all public now"* while reading an advisory still marked `triage`.
- **access drift** — security-team roster members
  (the collaborator list fetched once per run, see [`gather.md`](gather.md#step-1--gather-the-current-state))
  missing from the advisory's `collaborating_users`.
  Informational at the collaborator tier (adding collaborators is an admin hand-off).

**Record the advisory link(s) as a dedicated, clickable tracker field** — e.g. a `### GitHub Security Advisory (GHSA)` section —
listing each advisory as a markdown link
(`- [GHSA-…](https://github.com/<upstream>/security/advisories/GHSA-…)`), not buried in prose.
Populate it on every GHSA-sourced tracker (retroactively on first touch).

---

## Step 4 add-on — advisory writes (propose-then-confirm each)

Each is a separate confirmable proposal item (SKILL Golden rule 1).

1. **Link cve_id + reconcile fields — collaborator tier, sync performs it.**
   `gh api -X PATCH /repos/<upstream>/security-advisories/<GHSA> -f cve_id=<CVE>`,
   and where they diverge, mirror the tracker's authoritative `severity` / `cwe_ids` / `vulnerabilities` / `credits` onto the advisory.
   **Never** copy an advisory-supplied CVSS back into the tracker's severity field (the project's severity rule governs the tracker; the advisory mirrors *it*).
2. **Mirror state (publish / close) — admin tier, HAND OFF.** Do not PATCH `state` at the collaborator tier.
   Route it through the [Admin hand-off relay](#admin-hand-off--relay-the-needed-change-to-the-advisory-admin-team) below;
   many foundation advisories stay `triage` by design (the CVE ships through the foundation's own CVE tool, not GitHub's advisory flow), so publishing is often not even desirable.
3. **Provide collaborator access — admin tier, HAND OFF.** Route the missing-roster access drift through the
   [Admin hand-off relay](#admin-hand-off--relay-the-needed-change-to-the-advisory-admin-team).

---

## Admin hand-off — relay the needed change to the advisory-admin team

Step 4 items 2 (state / publish / close) and 3 (collaborator management) are **admin / security-manager** operations the collaborator tier cannot perform.
Do **not** leave them as a passive recap line, and do **not** post a `<tracker>` comment @-mentioning project members, who typically lack advisory admin rights too.
**Relay the needed change to the team that administers GitHub Private Vulnerability Reporting for the hosting org** —
for ASF projects, the foundation security team, via the [`tools/gmail/asf-relay.md`](../../../../tools/gmail/asf-relay.md) path.

### Delivery — an email relay (draft, never auto-sent)

Create a **draft** email to the org's advisory-admin security team (`<foundation-security-list>`) with `oauth-draft-create` —
never send directly (SKILL Golden rule 1), and never use the Gmail MCP, which mangles the `security/advisories/GHSA-…` URLs into redirects.
**Include the resolved `security_cc`** per the shared
[security draft CC resolution](../../../../tools/mail-source/contract.md#security-draft-cc-resolution);
block the draft if no address resolves.
Reply on the originating `<security-list>` thread when the report was relayed there (`--thread-id <id>`);
otherwise it is a **new** message (omit `--thread-id`) with a self-describing subject.
The hand-off is never a `<tracker>` comment; the tracker gets at most a one-line rollup note recording that the relay draft was prepared.

### What the relay says (three parts, terse)

1. **What the sync already did** — the collaborator-tier field edits applied
   (e.g. *"linked `cve_id=<CVE>` onto GHSA-…; recorded @… as a co-finder"*),
   each advisory as a clickable `…/security/advisories/GHSA-…` URL.
2. **The admin-only change + why the sync can't** — the exact action
   (*"close GHSA-… as a duplicate of GHSA-…"*, *"publish GHSA-…"*, *"add @…
   to collaborating_users"*) and that the operator holds only advisory-
   **collaborator** rights (state / collaborator PATCHes return `403`).
3. **The ask** — one line asking the advisory admins to perform it.

### Guardrails

- **Propose-then-confirm** the draft (recipient, CC, subject, body); the
  operator reviews the Gmail draft and sends it.
- **Idempotent** — record a prepared hand-off with a `<tracker>` rollup
  marker (`<!-- <marker-prefix>: ghsa-admin-handoff v1 -->`) naming the GHSA
  id + requested action; do not re-draft the same pending action.
- **Collaborator-doable ≠ hand-off** — field writes the operator CAN do
  (`cve_id`, `credits`, `severity`, `cwe_ids`, `vulnerabilities`) are just
  applied; the relay fires **only** for the admin-only cases above.

---

## Reporter reply — direct-post primary, relay fallback

There is **no** REST API for the advisory discussion thread, so the reply cannot be posted programmatically at any tier.
When the operator is an advisory collaborator, this replaces the email relay as the *primary* path:

- **Primary (operator IS a collaborator).** Do **not** draft a relay email.
  The sync (a) surfaces the exact reply text, (b) **opens the advisory discussion in the browser** (`open`/`xdg-open` on the advisory `html_url`),
  and (c) prints the **copy-pastable** reply block for the operator to paste into the already-open thread
  (advisory discussions have no comment-prefill URL parameter).
  The sync never claims to have *posted* the reply.
- **Fallback (operator is NOT a collaborator on that advisory).** Use the
  [`tools/gmail/asf-relay.md`](../../../../tools/gmail/asf-relay.md) email relay to the hosting security team.
  Surface which path was taken in the proposal + recap.

Non-GitHub forwarders (HackerOne, huntr, direct email relays) are
unaffected — they keep the [`tools/forwarder-relay/`](../../../../tools/forwarder-relay/README.md)
path.

---

## Guardrails

- **Propose-then-confirm every advisory write** (Golden rule 1) — the advisory is a surface on a public project.
- **Confidentiality** — private-advisory content never lands on a public surface.
- **Source of truth** — the tracker + CVE record is authoritative for CVE fields; the advisory is reconciled *to* it.
- **No blind state writes** — never PATCH `state`/publish speculatively; a success is permanent and public.
  Publishing is an explicit admin hand-off, opt-in per tracker.
