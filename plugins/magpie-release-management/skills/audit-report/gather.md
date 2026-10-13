<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 1 — reading the sources

Load this when Step 1 runs. Everything below is reading; nothing is written anywhere (Golden rule 1).

## The planning issue

Read the planning issue body and comments for each field of the Step 1 table.
Short references on the issue (`<org>/<repo>#<n>`) are fine to read; record the canonical URL.
`artefacts` is the RC artefact list the issue records: filename, SHA-512 and `.asc` file for each.
`vote_binding_plus1` / `vote_binding_minus1` come from the vote tally on the planning issue or the `[RESULT]` thread.

## Mail-archive resolution

Before marking `vote_thread_url`, `result_thread_url`, or `announce_archive_url` as `MISSING`,
resolve each one from the configured mail archive when it is not already on the planning issue.
`audit-report gather` names, per field, the `subject` to look for, the `query` to search with (the subject up to anything it could not render),
every list to search (`lists`, with `archive_urls` rendered from `mail_archive_url_template`) and the permalink shape that counts.
Search the archive named by `mail_archive` (for ASF, PonyMail on `lists.apache.org`) for that subject,
take the matching thread's permalink (`https://lists.apache.org/thread/<id>`), and record it.
The `[ANNOUNCE]` may index under `announce_list` **or** a cc'd list (e.g. `dev@`), so search every list `gather` names before giving up.
Mark the field `MISSING` **only** when the archive returns no match — e.g. the message was sent so recently it is not yet indexed —
and note in the record that it should be backfilled once indexed.
This keeps the audit record self-completing rather than depending on the URLs having been pasted onto the planning issue.
A list page or a search URL is not a permalink: `audit-report check` flags one under `problems`.

## Promote revision

When the planning issue does not record it and `gather` printed a `promote_revision.command`
(`svn info --show-item last-changed-revision <dist-release-url>` for `svnpubsub`), that is the read that resolves it:
the revision of the Step 10 `svn mv` commit that created the promoted directory.
Other backends: the backend-equivalent identifier from the planning issue, else `MISSING`.

## Binding voters

Take the binding voters the `[RESULT] [VOTE]` names (their `From:` addresses or Apache IDs), save them as a JSON list, and run

```bash
uv run --project <framework>/tools/release-management release-management audit-report voters \
  --voters <scratch>/result-voters.json --roster <roster_path>
```

It resolves each against the roster the way `release-vote-tally` does (primary email, else `<id>@apache.org`) and prints `binding_voters` as roster handles,
or `MISSING` when none resolves.
A voter in `unresolved` is never cited, and never by address (Golden rule 5): surface it to the RM.

## Privacy gate

A field whose only source is the security tracker, a CVE draft, a GHSA record, reporter mail or embargoed text is `REDACTED`, never read further;
note a one-line reason for it (it becomes `redaction_reasons` in Step 2).
A field whose source simply does not exist is `MISSING`.
