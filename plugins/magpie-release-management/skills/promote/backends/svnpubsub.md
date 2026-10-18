<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Promotion backend — `svnpubsub` (ASF default)

The render's `command_block` holds three steps:

1. `svn mv` of the RC from `dist/dev/<project>/<version>-rc<N>/` to `dist/release/<project>/<version>/`,
   under `--username <apache_id>`, with a `-m` message naming the `[RESULT] [VOTE]` archive URL.
2. `svn list` of the target, to verify the move landed.
3. The **final** `<version>` tag, cut and pushed on the **same** commit the approved RC was built from (no rebuild),
   signed with the RM's release key (`git -c gpg.format=openpgp tag -s -u <rm_gpg_fingerprint>`), pushed to `git_upstream_remote`, then verified with `tag -v`.
   Downstream links (changelog, `[ANNOUNCE]`, site) reference this final tag, never `<version>-rc<N>`.

When a held convenience artefact is staged in the RC directory, a step comes first:
an `svn rm` of it, its `.asc` and its `.<digest>` files (one per `digest_set` entry) in `dist/dev/`, chained to the `svn mv` with `&&` so a failed removal stops the move
(see [`../convenience-artefacts.md`](../convenience-artefacts.md)).

Pass the facts Step 1 read: `--apache-id`, `--result-vote-url` and `--rc-commit-sha` (`git rev-list -n1 <version>-rc<N>`).
A fact still missing comes back as a placeholder in the block and a `warnings` entry; ask the RM for it rather than guessing.

The promote commit is the moment the RM runs `svn mv`; the mirror note's one-hour clock starts there.

The target, identified by its `dist/release/` prefix, is on the hard denylist for the agent (Golden rule 2):
the block is text for the RM, and the agent never runs any line of it, whatever svn credentials the session holds.
When Step 0 handed off (`rm_is_pmc: false`), the same block follows the hand-off note for a PMC member to run;
see [`../outcomes/handoff-non-pmc.md`](../outcomes/handoff-non-pmc.md).
