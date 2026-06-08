<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the **Stage 3 live merge-readiness classification** of the
`pr-management-quick-merge` skill from the Apache Steward framework.

A PR that passed Stages 1 and 2 (quality gate + triviality) reaches Stage 3.
You are given the **live** `GET /repos/<repo>/pulls/<N>` response, which
forces GitHub to compute `mergeable` and `mergeable_state` fresh — the batch
values cannot be trusted for this step.

## Classification rules

Classify each candidate by the live `(mergeable, mergeable_state)` pair:

| Live state | Bucket |
|---|---|
| `mergeable == true`, `mergeable_state ∈ {clean, has_hooks}` | **ready** — surface with the merge command |
| `mergeable == true`, `mergeable_state ∈ {unstable, behind}` | **ready** — note the state; `unstable` means a non-required check is still running but every required check is green; `behind` is a stale-but-clean branch GitHub will fast-forward |
| `mergeable == true`, `mergeable_state == blocked` **and** `reviewDecision == REVIEW_REQUIRED` | **needs-approval** — the branch merges cleanly but a required committer review is missing; route to the `[A]pprove` action |
| `mergeable == true`, `mergeable_state == blocked` **and** `reviewDecision != REVIEW_REQUIRED` | **drop** — the block is not cleared by an approval; reason `gate:G5-conflict` (a non-approval required check is the blocker) |
| `mergeable == false` **or** `mergeable_state == dirty` | **drop** — genuine merge conflict; reason `gate:G5-conflict` |
| `mergeable == null` **or** `mergeable_state == unknown` | **drop** — mergeability still computing; reason `gate:G5-unknown`; conservative per Golden rule 4. It will settle on the next run. |

## Output format

Return ONLY valid JSON:

```json
{
  "bucket": "ready | needs-approval | drop",
  "drop_reason": null,
  "reason": "<one sentence>"
}
```

- `drop_reason` is one of `gate:G5-conflict`, `gate:G5-unknown`,
  or `null` when `bucket != "drop"`.
- `reason` is one concise sentence naming the classification outcome.
- Do not include any text outside the JSON object.
