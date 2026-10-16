<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Staging with ATR

**The full ATR flow (`release_dist_backend = atr`).**
ATR's Compose phase *is* the staging, and ATR is the only staging location:
the render's `staging_commands` are `atr release start`, one `atr upload` per artefact, signature and checksum (`atr upload PROJECT VERSION PATH FILEPATH`),
and the `atr check status` / `atr check concerns` reads.
Nothing is written to SVN `dist/dev/`, and no `--asf-id` is needed: the `atr` client carries the RM's own credentials.
`atr_upload_commands` stays empty, because the staging block already uploads to ATR and a second copy is what the full flow exists to avoid.
See the [ATR release runbook](../../../../../docs/release-management/atr-release-runbook.md#step-c-compose-the-release-candidate-steps-4-6).

**The hybrid (`release_dist_backend = svnpubsub`, `release_vote_backend = atr`).**
`svnpubsub` hosts and promotes, ATR runs the checks and drives the vote.
The signed artefacts land in **both** the dist backend and ATR, so ATR's Compose checks run and there is a candidate revision to vote on.

In both cases ATR's Finish/publish is never emitted here: promotion is `release-promote`'s step, after the vote.

The uploaded candidate is the one `release-vote-draft` votes on;
`atr vote start` targets the latest uploaded revision by default (its `--revision` flag is optional),
so there is no separate revision id to capture here.

The block is a proposal like the rest; the RM runs it on their machine under their own ATR credentials.
`atr_platform_url` from `release-management-config.md` is the target platform.
