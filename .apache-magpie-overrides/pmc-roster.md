<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie: PMC roster](#apache-magpie-pmc-roster)
  - [Roster](#roster)
  - [Resolution](#resolution)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie: PMC roster

**This file is a placeholder ahead of the release-management
skill family landing.** None of the `release-*` skills exist
yet, see
[`docs/release-management/README.md`](../docs/release-management/README.md).
The roster below is what `release-vote-tally` will read to
classify each `[VOTE]` reply as binding (PMC member) or
non-binding (committer / community).

PMC membership for Apache Magpie. Update every time a new PMC
member is added per a `[VOTE]` thread on the project's private list
or per a Board resolution removing a member. Authoritative source
is the project's record under `<projects.apache.org>`; this file
mirrors it so the tally skill can resolve a `From:` address without
hitting the public LDAP every run.

## Roster

| Apache ID | Name | Primary email | Binding since |
|---|---|---|---|
<!-- Derived 2026-09-27 from projects.apache.org committee `magpie` (chair: potiuk). -->
| `amoghdesai` | Amogh Desai | `amoghdesai@apache.org` | `2026-06-17` |
| `akm` | Andrew Musselman | `akm@apache.org` | `2026-06-17` |
| `kirs` | Calvin Kirs | `kirs@apache.org` | `2026-06-17` |
| `csutherl` | Coty Sutherland | `csutherl@apache.org` | `2026-06-17` |
| `clr` | Craig L Russell | `clr@apache.org` | `2026-06-17` |
| `eladkal` | Elad Kalif | `eladkal@apache.org` | `2026-06-17` |
| `rusackas` | Evan Rusackas | `rusackas@apache.org` | `2026-06-17` |
| `iemejia` | Ismaël Mejía | `iemejia@apache.org` | `2026-06-17` |
| `jamesfredley` | James Fredley | `jamesfredley@apache.org` | `2026-06-17` |
| `potiuk` | Jarek Potiuk | `potiuk@apache.org` | `2026-06-17` |
| `jbonofre` | Jean-Baptiste Onofré | `jbonofre@apache.org` | `2026-06-17` |
| `jmclean` | Justin Mclean | `jmclean@apache.org` | `2026-06-17` |
| `zeroshade` | Matthew Topol | `zeroshade@apache.org` | `2026-06-17` |
| `paulk` | Paul King | `paulk@apache.org` | `2026-06-17` |
| `gopidesu` | Pavan Kumar | `gopidesu@apache.org` | `2026-06-17` |
| `pkarwasz` | Piotr Karwasz | `pkarwasz@apache.org` | `2026-06-17` |
| `remm` | Rémy Maucherat | `remm@apache.org` | `2026-06-17` |
| `rbowen` | Rich Bowen | `rbowen@apache.org` | `2026-06-17` |
| `rzo1` | Richard Zowalla | `rzo1@apache.org` | `2026-06-17` |
| `russellspitzer` | Russell Spitzer | `russellspitzer@apache.org` | `2026-06-17` |
| `tison` | Zili Chen | `tison@apache.org` | `2026-06-17` |

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
