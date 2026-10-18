<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# KEYS backend — `release_dist_backend = atr`

**Offer the ATR path first.**
ATR can hold the committee `KEYS` file and manage it for the project once the RM loads their own key into ATR — an opt-in on the committee configuration page.
Where that is enabled, the RM adds the key in ATR rather than committing `KEYS` by hand, and the `svn` sequence is not used.
Ask which the project has configured rather than assuming;
both remain valid, and a project that has not opted in still commits to SVN exactly as in [`svnpubsub.md`](svnpubsub.md).

The render sets `atr_offer: true` and still prints the `svn` sequence for the project that has not opted in.
