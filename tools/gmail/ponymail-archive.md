<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gmail — ASF PonyMail archive URL construction](#gmail--asf-ponymail-archive-url-construction)
  - [URL shapes](#url-shapes)
    - [Archive search (query returns a list-page with matching threads)](#archive-search-query-returns-a-list-page-with-matching-threads)
    - [Archive API (JSON response, the sync skill uses this first)](#archive-api-json-response-the-sync-skill-uses-this-first)
    - [Resolved thread URL (what the skill records in the tracker)](#resolved-thread-url-what-the-skill-records-in-the-tracker)
  - [Use case — `security-issue-import`](#use-case--security-issue-import)
  - [Use case — `security-issue-sync`](#use-case--security-issue-sync)
  - [When the archive is not available](#when-the-archive-is-not-available)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gmail — ASF PonyMail archive URL construction

The ASF hosts mailing-list archives at
[`lists.apache.org`](https://lists.apache.org/) (internally
**PonyMail**). The skills use it for two distinct lookups:

1. **Private `security@<project>.apache.org` thread URL** — when
   importing a new report, resolve a pastable archive URL for the
   inbound Gmail thread so the tracker's *security-thread* body
   field can record both the private archive URL and the Gmail
   `threadId`. Access to the private list's archive requires PMC
   OAuth; non-PMC triagers cannot follow the URL.
2. **Public `users@<project>.apache.org` advisory URL** — once the
   release manager sends the advisory, the sync skill scans the
   public archive for the CVE ID and populates the tracker's
   *public-advisory-url* field. This URL anchors the `vendor-advisory`
   entry in the public CVE record.

Both lookups share the same URL-construction pattern.

Placeholder convention:

- `<list>` — the mailing-list address. For private lookups, the
  project's `security_list`; for public lookups, the project's
  `users_list` or `announce_list` (see the project manifest's
  *Mailing lists* section).
- `<list-domain>` — the list's domain component (for
  `<security-list>`, the value is
  `<security-list-domain>`); used inside the URL's query
  string.

## URL shapes

### Archive search (query returns a list-page with matching threads)

```text
https://lists.apache.org/list?<list>:YYYY-M:<url-encoded search>
```

- `YYYY-M` is the year plus a 1- or 2-digit month (e.g. `2026-4`
  for April 2026 — **no leading zero**).
- `<url-encoded search>` is a URL-encoded search string (spaces as
  `%20`; PonyMail tolerates `()`, `:`, and `/` in the query string
  without encoding).

Alternative bare URL form used by the sync skill when scanning the
public archive for a CVE ID:

```text
https://lists.apache.org/list.html?<list>:YYYY:<CVE-ID>
```

### Archive API (JSON response, the sync skill uses this first)

```text
https://lists.apache.org/api/thread.lua?list=<list-local>&domain=<list-domain>&q=<search>
```

Where `<list-local>` is the portion before the `@` (e.g. `users`)
and `<list-domain>` is the portion after (e.g. `<project-domain>`).

Request via `gh api <url>` (authenticates as the user — helpful for
private lists if they ever open up) or plain `curl -s <url>` for
public lists.

### Resolved thread URL (what the skill records in the tracker)

```text
https://lists.apache.org/thread/<hash>?<list>
```

- `<hash>` is PonyMail's per-thread opaque ID.
- The `?<list>` suffix is load-bearing — PonyMail requires it to
  disambiguate threads that exist on multiple lists.

This is the URL the skills store in the *security-thread* body
field (for private lookups) and in the *public-advisory-url* body
field (for public lookups). Field-role names are defined in
[`../github/issue-template.md`](../github/issue-template.md#field-roles-the-skills-use);
project-specific concrete field names live in the project manifest.

## Use case — `security-issue-import`

The security list's PonyMail archive is not anonymously queryable
(the list is gated behind ASF LDAP), so the skill **cannot** fetch
the archive URL programmatically. Instead, the skill **constructs**
the search URL for the month the message was received and proposes
it to the user at Step 5 as a one-click lookup:

```text
https://lists.apache.org/list?<security-list>:YYYY-M:<url-encoded subject>
```

The user opens the URL in an ASF-logged-in browser, clicks into the
thread, and pastes the resulting
`https://lists.apache.org/thread/<hash>?<security-list>` URL back.
The skill records **both** lines in the *security-thread* field — the
PonyMail URL on the first line, and *"Gmail thread `<threadId>`"* on
the second line for cross-reference.

Fallback when the user does not paste a URL back (the message is not
in the archive yet, LDAP access is unavailable, etc.): the skill
records the Gmail-threadId-only textual note:

> No public archive URL — tracked privately on Gmail thread `<threadId>`.

Either way, the URL in this field is **internal-only** — the
CVE-JSON generator does not export it to `references[]`. See the
*"CVE references must never point at non-public mailing-list
threads"* rule in [`../../AGENTS.md`](../../AGENTS.md).

## Use case — `security-issue-sync`

The public `users@` archive **is** anonymously queryable. On every
sync run, if the tracker has `announced - emails sent` but the
*public-advisory-url* field is still empty, the skill scans the
archive for the CVE ID:

```bash
gh api "https://lists.apache.org/api/thread.lua?list=<users-list-local>&domain=<users-list-domain>&q=<CVE-ID>" 2>/dev/null \
  || curl -s "https://lists.apache.org/list.html?<users-list>:YYYY:<CVE-ID>"
```

If the query returns a hit, the skill proposes populating the
*public-advisory-url* field with the
`lists.apache.org/thread/<id>?<users-list>` URL, regenerating the CVE
JSON attachment (so the URL flows into `references[]` as
`vendor-advisory`), and adding the `announced` label.

Once the field is populated, the sync skill treats it as
authoritative — no further archive scans needed.

## When the archive is not available

Not every project using this framework will run on ASF infrastructure.
If the project uses a different list archive (Mailman, Discourse,
MailArchive…), replace this file with the equivalent URL patterns for
that backend. The generic contract the skills rely on is:

1. Given a list and a search term, return a URL that a human can
   open in a browser to resolve the thread.
2. (Public lists only) Given a list and a CVE ID, return a machine-
   readable response the skill can use to detect an advisory has
   landed.

The skills branch on presence/absence: if the public-archive scan
returns no result, they leave the field empty and surface the gap at
the next sync.
