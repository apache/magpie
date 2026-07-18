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

The PMC roster `release-vote-tally` reads to classify each `[VOTE]`
reply as binding (PMC member) or non-binding (committer / community).
Template: [`projects/_template/pmc-roster.md`](../_template/pmc-roster.md).

Authoritative source is the project's official committee roster
(`https://whimsy.apache.org/roster/committee/magpie`). This file
mirrors it so the tally skill can resolve a `From:` address without
hitting LDAP every run. Keep it in sync; membership changes land in
Whimsy first. The roster below reflects the founding PMC recorded in
[`MISSION.md`](../../MISSION.md).

## Roster

| Apache ID | Name | Primary email | Binding since |
|---|---|---|---|
| `potiuk` | Jarek Potiuk (Chair) | `potiuk@apache.org`, `jarek@potiuk.com` | `[resolution]` |
| `pkarwasz` | Piotr Karwasz | `pkarwasz@apache.org` | `[resolution]` |
| `eladkal` | Elad Kalif | `eladkal@apache.org` | `[resolution]` |
| `zeroshade` | Matthew Topol | `zeroshade@apache.org` | `[resolution]` |
| `gopidesu` | Pavan Kumar Gopidesu | `gopidesu@apache.org` | `[resolution]` |
| `amoghdesai` | Amogh Desai | `amoghdesai@apache.org` | `[resolution]` |
| `akm` | Andrew Musselman | `akm@apache.org` | `[resolution]` |
| `jmclean` | Justin Mclean | `jmclean@apache.org` | `[resolution]` |
| `jbonofre` | Jean-Baptiste Onofré | `jbonofre@apache.org` | `[resolution]` |
| `paulk` | Paul King | `paulk@apache.org` | `[resolution]` |
| `rusackas` | Evan Rusackas | `rusackas@apache.org` | `[resolution]` |
| `russellspitzer` | Russell Spitzer | `russellspitzer@apache.org` | `[resolution]` |
| `iemejia` | Ismael Mejia | `iemejia@apache.org` | `[resolution]` |
| `tison` | Zili Chen (tison) | `tison@apache.org` | `[resolution]` |
| `jamesfredley` | James Fredley | `jamesfredley@apache.org` | `[resolution]` |
| `kirs` | Calvin Kirs | `kirs@apache.org` | `[resolution]` |
| `rbowen` | Rich Bowen | `rbowen@apache.org` | `[resolution]` |
| `mdrob` | Mike Drob | `mdrob@apache.org` | `[resolution]` |
| `clr` | Craig L Russell | `clr@apache.org` | `[resolution]` |
| `csutherl` | Coty Sutherland | `csutherl@apache.org` | `[resolution]` |
| `remm` | Rémy Maucherat | `remm@apache.org` | `[resolution]` |
| `rzo1` | Richard Zowalla | `rzo1@apache.org` | `[resolution]` |

**A `+1` from a PMC member is binding; from anyone not on this roster,
non-binding.**

A `[VOTE]` reply counts as binding when:

1. The `From:` address matches any address in a row's `Primary email`
   cell exactly — the cell may list several comma-separated addresses
   (e.g. an `@apache.org` address plus a personal address the member
   votes from), **or**
2. The `From:` address contains `@apache.org` and the local part
   matches a row's `Apache ID` exactly.

Rule (2) is the fallback because PMC members occasionally vote from
`<id>@apache.org` rather than the `Primary email` recorded here.

> [!IMPORTANT]
> `Primary email` is set to each member's `@apache.org` address, so
> rules (1) and (2) both resolve an `@apache.org` vote. **A member who
> intends to vote from a personal Gmail or corporate address MUST have
> that address added to their `Primary email` here before the 0.1.0
> `[VOTE]`** — otherwise neither rule matches and their `+1` tallies
> non-binding. `Binding since` is `[resolution]` for the founding
> roster; replace with the establishment-resolution date once
> confirmed (informational only; not used for resolution).

## Resolution

`release-vote-tally`'s resolution algorithm:

1. Normalise the `From:` header to `local@domain` form.
2. Try exact match (case-insensitive) against each comma-separated
   address listed in the `Primary email` cell.
3. If `domain == apache.org`, try the local part against the
   `Apache ID` column.
4. If neither hits, the vote is classified non-binding, flagged
   `BINDING-CANDIDATE-UNRESOLVED`, and surfaced for RM review; the
   skill refuses to count it until the RM updates this roster or
   confirms the vote is non-binding.

The roster is the source of truth for the tally skill. The skill never
infers binding status from message content (a sign-off that says "PMC
member" does not promote a non-roster voter to binding).

> [!NOTE]
> Reconcile against the Whimsy roster before relying on this for a
> binding tally. Membership changes (additions, emeritus) land in
> Whimsy first.
