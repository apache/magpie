<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>`: PMC roster](#todo-project-name-pmc-roster)
  - [Roster](#roster)
  - [Resolution](#resolution)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>`: PMC roster

**This file is a placeholder ahead of the release-management
skill family landing.** None of the `release-*` skills exist
yet, see
[`docs/release-management/README.md`](../../docs/release-management/README.md).
The roster below is what `release-vote-tally` will read to
classify each `[VOTE]` reply as binding (PMC member) or
non-binding (committer / community).

PMC membership for `<Project Name>`. Update every time a new PMC
member is added per a `[VOTE]` thread on the project's private list
or per a Board resolution removing a member. Authoritative source
is the project's record under `<projects.apache.org>`; this file
mirrors it so the tally skill can resolve a `From:` address without
hitting the public LDAP every run.

## Roster

| Apache ID | Name | Primary email | Binding since |
|---|---|---|---|
| `<TODO>` | `<TODO Member Name>` | `<TODO>@apache.org` | `<TODO YYYY-MM-DD>` |
| `<TODO>` | `<TODO Member Name>` | `<TODO>@apache.org` | `<TODO YYYY-MM-DD>` |
| `<TODO>` | `<TODO Member Name>` | `<TODO>@apache.org` | `<TODO YYYY-MM-DD>` |

A `[VOTE]` reply counts as binding when:

1. The `From:` address matches a row's `Primary email` exactly, **or**
2. The `From:` address contains `@apache.org` and the local part
   matches a row's `Apache ID` exactly.

Rule (2) is the fallback because PMC members occasionally vote from
`<id>@apache.org` rather than the `Primary email` recorded here.
Personal Gmail / corporate addresses MUST appear in `Primary email`
to count.

## Resolution

`release-vote-tally`'s resolution algorithm:

1. Normalise the `From:` header to `local@domain` form.
2. Try exact match against `Primary email` (case-insensitive).
3. If `domain == apache.org`, try the local-part against the
   `Apache ID` column.
4. If neither hits, the vote is classified non-binding and
   surfaced for RM review.

If a binding voter casts a vote from an address not on this roster,
the skill flags `BINDING-CANDIDATE-UNRESOLVED` and refuses to count
the vote until the RM either (a) updates this roster to include the
address, or (b) confirms the vote is non-binding.

The roster is the source of truth for the tally skill. The skill
never infers binding status from message content (e.g. a sign-off
that says "PMC member" does not promote a non-roster voter to
binding).
