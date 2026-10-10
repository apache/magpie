<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tier A — documentation and text

Every changed file matches `tier_a_allow_globs`: `.rst` / `.md` docs, the changelog, newsfragments, translations, the spelling wordlist.
The change cannot affect runtime behaviour — the blast radius is "wrong words on a page" — so a Tier A diff is usually a glance.
A Tier A candidate is still read before it is merged: a docs PR can state something wrong.
