<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — capture the public advisory URL

Part of the Step 2b lookup in [`signals-to-actions.md`](signals-to-actions.md), which says when to read this file.

  1. If `announced - emails sent` is set and the field is still empty, **scan the public advisory archive for the CVE ID**, using the archive the project declares in [`<project-config>/project.md`](../../../../<project-config>/project.md#archive-system) (`archive_system`):

     - **PonyMail, the ASF default (`archive_system.kind: ponymail`).** If Step 0
       recorded `ponymail_authenticated: true`, call:

       ```text
       mcp__ponymail__search_list(
         list: "users",
         domain: "<project>.apache.org",
         query: "<CVE-ID>",
         timespan: "lte=30d"
       )
       ```

       `users@` is public, so no LDAP allowlist check is needed.
       Call shape: [`tools/ponymail/operations.md` — Find the advisory archive thread](../../../../tools/ponymail/operations.md#find-the-advisory-archive-thread-on-usersprojectapacheorg).
       When PonyMail MCP is disabled, unauthenticated, or errors, use the anonymous-HTTPS HTTP API + `list.html` pattern in
       [`tools/gmail/ponymail-archive.md`](../../../../tools/gmail/ponymail-archive.md#use-case--security-issue-sync);
       it works for every triager regardless of LDAP status.

     - **Any other archive (`archive_system.kind` not `ponymail`).** Query the project's `search_url_template` with the CVE ID, open the hit's thread, and take its id. When the archive declares no `search_url_template`, or no hit resolves, ask the release manager for the archived advisory URL instead of guessing.

     A single hit is the advisory thread. Build the public advisory URL with the manifest's `advisory_thread_url_template` (or the legacy `ponymail_thread_url_template` when the project declares only that key).
     When neither key is declared, use the thread permalink the archive returned, or ask the release manager; never construct one.

     **A search hit is a candidate, not the advisory.** The search matches any public post that mentions the CVE ID
     (a user question, a reply, a forward), and capturing this URL is what moves the CVE record to `public`.
     For each hit, fetch the thread (`mcp__ponymail__get_thread`, the HTTP API, or the archive's own thread page) for its list, root subject and root sender,
     write `{cve_id, url, thread: {list, subject, from}, advisory_list: <users-list>, mail_archive_url, authorized_senders}` to a file and run
     `security-management issue-sync advisory-archive --input <file>`;
     `authorized_senders` is every release-manager and security-team address from [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md).
     Only an `accepted: true` candidate may be proposed: the thread is on `<users-list>`, its root subject is the advisory's own `<CVE-ID>: <description>`
     (the subject the CVE tool sends; never a `Re:` / `Fwd:`), its root message is from an authorized sender, and the URL is under `<mail-archive-url>`.
     A rejected hit is listed with its `reasons` in the observed state and proposes nothing.
     Show the accepted URL **with its list, subject and sender** to the user as its own numbered item,
     and say that the sender comes from the archived `From:` header and is not cryptographically verified,
     so the user should recognise the announcement itself before confirming;
     record it — and run the close-out that follows from it — only once the user explicitly confirms that URL.
     On that confirmation, populate the field with the thread URL (per `advisory_thread_url_template`, or the legacy `ponymail_thread_url_template`),
     regenerate the CVE JSON attachment, and add the `announced` label.
