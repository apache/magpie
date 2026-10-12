<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Staging with `release_vote_backend = atr`

The hybrid flow: `release_dist_backend = svnpubsub` hosts and promotes, ATR runs the checks and drives the vote.
The signed artefacts land in **both** the dist backend and ATR, so ATR's Compose checks run and there is a candidate revision to vote on.
ATR's Finish/publish is never emitted: promotion stays with `release_dist_backend`.

The uploaded candidate is the one `release-vote-draft` votes on;
`atr vote start` targets the latest uploaded revision by default (its `--revision` flag is optional),
so there is no separate revision id to capture here.

The block is a proposal like the rest; the RM runs it on their machine under their own ATR credentials.
`atr_platform_url` from `release-management-config.md` is the target platform.
