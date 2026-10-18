<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Delivery — `vote_backend = atr`

The drafted subject + body go to the ATR platform, which *sends* the `[VOTE]` to `<vote_list>` and *tabulates* replies.
The skill still sends nothing: the Step 2 render's `atr_vote_command` is a paste-ready `atr vote start` command for the RM to run under their own ATR credentials
(`-m <vote_list>`, `--duration <vote_window_hours>`, the final subject, and `--no-auto-publish`, which is REQUIRED for the hybrid: ATR must NOT publish, SVN owns promotion).
Pass `--atr-revision <rev>` only when the RM names one: it defaults to the latest uploaded revision, so do not hard-depend on a `revisions` lookup.
Verb and flag names may shift between ATR releases; tell the RM to confirm them with `atr vote start --help`,
and to acknowledge any concern-group keys `atr check concerns <project> <version>` lists with `--concerns-noted`.

The `<staging_url>` in the body must still point at the dist backend's download location (e.g. `dist/dev/<project>/…` under the hybrid), so voters fetch the canonical artefacts even though ATR drives the thread;
the render keeps it, and adds the *ATR check results for this candidate* line (`--atr-candidate-url`, from the planning issue; the render refuses without it).
ATR's own default vote text links only the candidate page, so the RM supplies the drafted body, with its *How to verify* section, to ATR (the client's body option, or the vote form on the candidate page; confirm with `atr vote start --help`).

This is a proposal like the email: present it and get RM confirmation before it is run.
Posting the `[VOTE]` is a state change the RM performs, never the skill.
