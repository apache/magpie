<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — next-step recommendation

## Step 2 — Build a proposal (do not apply anything yet)

### 2c. Next-step recommendation

A single short paragraph describing what the user should do *after* these
updates land, based on the process step. Examples:

- *"Step 3: start the CVE-worthiness discussion in a comment on the issue, tagging at least one other security team member."*
- *"Step 4: escalate to a wider audience — the discussion has been stalled for 34 days. Run the two-phase escalation per [`docs/security/process.md` — Step 4](../../../../docs/security/process.md#step-4--escalate-stalled-discussions): phase 1 is a short call for ideas to `<private-list>` (no AI analysis), phase 2 — only if phase 1 stays silent for ~7 more days — is an AI-generated design-space analysis that the triager reviews before posting. The agent drafts both phases as proposals; the triager confirms the exact wording + the list of people to `@`-mention before anything is sent."*
- *"Step 6: allocate a CVE. Run the [`security-cve-allocate`](../cve-allocate/SKILL.md) skill (it prints the `<cve-tool>` form URL plus a CVE-ready title and wires the allocated ID back into the tracker)."*
- *"Step 10: close the private PR at <tracker>#NNN now that <upstream>#NNNN has merged."*
- *"Step 11: `pr merged` — tracker parked until the release train ships. No action needed from the security team; the next sync run will detect the PyPI / Helm release and propose the `fix released` swap (Step 12)."*
- *"Step 12: `fix released` — the release carrying the fix is now on PyPI / the Helm registry. Ownership of the issue has transferred to the release manager; the label swap was the hand-off."*
- *"Step 13: the release manager should now fill in the CVE tool fields taken from the issue — CWE, product, versions, severity, patch link, credits — move the CVE to REVIEW → READY, and send the advisory to `<announce-list>` / `<users-list>`."*
- *"Step 14: scan the users@ archive for the CVE ID, populate the *Public advisory URL* body field, regenerate the CVE JSON attachment, and move the issue to `announced`. Sync does all of this automatically on the next run once the advisory is archived."*
- *"Step 15: release manager — copy the regenerated CVE JSON into Vulnogram, close the issue."*

**Never guess the release manager.** When a next-step recommendation or a
status-comment references "the release manager for `<version>`", look up
the actual person, in this order:

1. **Check [`<project-config>/release-trains.md` § *Release managers for releases currently relevant to the security tracker*](../../../../<project-config>/release-trains.md#release-managers-for-releases-currently-relevant-to-the-security-tracker) first** — if the release is already
   listed there, use that name; it is the cache the next two sources fill.
2. **Check the project's release plan** at
   `<project-wiki>`, which names the release manager for each *upcoming* cut.
   Use it when the release has not been cut yet, or for the rotation roster.
3. **Check the `[RESULT][VOTE]` thread on `<dev-list>`** —
   the sender of the `[RESULT][VOTE] Release <product> <version>` (or
   `[RESULT][VOTE] <product> <scope-b> - release preparation date
   <YYYY-MM-DD>`) message **is** the release manager for that specific
   cut. Use this when the release has already shipped (the wiki tracks only upcoming releases). Two query paths:

   - **PonyMail MCP (preferred when enabled).** `dev@` is a public
     list; no LDAP allowlist check is needed. Call:

     ```text
     mcp__ponymail__search_list(
       list: "dev",
       domain: "<project-domain>",
       subject: "[RESULT][VOTE]",
       query: "<version-or-wave-token>",
       timespan: "lte=14d"
     )
     ```

     See
     [`tools/ponymail/operations.md` — Find the `[RESULT][VOTE]` thread](../../../../tools/ponymail/operations.md#find-the-resultvote-thread-for-a-release)
     for the full call shape. The sender of the top hit is the RM.

   - **Gmail (fallback).** When PonyMail MCP is disabled or
     unauthenticated, search Gmail:
     `"[RESULT][VOTE]" "<product> <scope-b>" from:<dev-list>`,
     narrowed by date if needed.
     It finds the thread only if the account is subscribed to `dev@`.

If the release manager you found is not yet in
[`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md),
propose appending them, with the `[RESULT][VOTE]` thread link and the release date, to its
"Release managers for releases currently relevant to the security tracker" subsection in the same sync run.
**Do not substitute a "plausible" name** (e.g. a frequent release manager from previous releases):
the role rotates per cut, and a wrong name leaves the advisory on nobody's desk.

**If a CVE needs to be allocated**, point the user at the
[`security-cve-allocate`](../cve-allocate/SKILL.md) skill on its own line:

> Allocate a CVE via the [`security-cve-allocate`](../cve-allocate/SKILL.md)
> skill. It opens the `<cve-tool>` form at
> `<cve-tool-url>`, pre-computes a CVE-ready
> title (stripped of `<vendor>: <product>:` / `[ Security Report ]` / version
> noise), and — once you paste back the allocated `CVE-YYYY-NNNNN` ID —
> wires it into the tracker (body field, label, status comment, CVE
> JSON embed).

**Whenever a CVE ID is mentioned** — in the proposal, in the status-change
comment on the `<tracker>` issue, or in the recap — render it as a clickable link per the "Linking CVEs" section of
[`AGENTS.md`](../../../../AGENTS.md).
The draft email to the reporter is the exception: it carries the bare CVE ID (the `cve.org` URL once published), never the `<cve-tool>` URL, per the same section.
Concretely:

- Before publication: link to the `<cve-tool>` record, e.g.
  `[CVE-2026-40690](<cve-tool-url>/cve5/CVE-2026-40690)`.
- After publication (issue has `vendor-advisory`, advisory has been sent to
  `<users-list>`): additionally link to the public `cve.org`
  record, e.g. `CVE-2025-50213 ([CVE tool](<cve-tool-url>/cve5/CVE-2025-50213),
  [cve.org](https://www.cve.org/CVERecord?id=CVE-2025-50213))`.

Do not emit bare `CVE-YYYY-NNNNN` text — always link.

Per **Golden rule 2** in [`SKILL.md`](SKILL.md), every `<tracker>` reference in the proposal is a clickable markdown link;
never emit a bare `#NNN` or `<tracker>#NNN`.

---
