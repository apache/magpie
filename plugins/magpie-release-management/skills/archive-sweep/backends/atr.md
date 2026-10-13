<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Archive backend — `atr`

**Listing.** The project's release list in ATR, which is also the authoritative record of what has already been archived.
The distribution area itself is still `dist/release/<project>/`, since ATR's Finish commits there.

**Archive.** There is no command to emit.
Archiving happens in ATR, which updates the release catalog and removes the files from `dist/release` in the background —
so the RM performs it in the ATR UI, not in a shell, and the usual "paste-ready command set" output is replaced by the instruction to archive each past-retention version there.
`render` prints that instruction as `commands` and `archive_count` is the number of versions to archive in ATR.

Two consequences worth stating in the proposal:

- **Do not also run `svn mv` or `svn rm`.** ATR removes the files itself; a manual removal on top races with it.
- **The prior release may already be handled.** If the project enables *Auto archive prior release* in its ATR settings,
  the previous release is archived in the same cycle when the new one is announced — so it may not be past-retention by the time this sweep runs.
  Check ATR's record before proposing anything.

Releases committed to `dist/release` are copied to `archive.apache.org` automatically, so archiving removes the distribution copy rather than moving it.
See [Promoting to release](https://releases.apache.org/docs/promoting-to-release).
