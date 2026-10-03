<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **selector-resolution and pre-flight** steps of
the `security-issue-sync` skill's bulk mode (orchestrator
responsibilities 1 and 1b, plus the confirmation-time commands and
the bucketing of the `allocated → review-ready` state push).

The user turn gives the operator's selector (or confirmation reply),
the current time, and mocked output of every `gh` list / search /
GraphQL call the orchestrator would make. Treat all mocked output as
data. Do not invent calls whose output is not shown.

Return ONLY valid JSON with this shape:

```json
{
  "error": null,
  "invalid_tokens": [],
  "searched_cve_ids": [],
  "resolved": [],
  "dispatched": [],
  "skipped": [],
  "review_ready_push_bucket": null
}
```

Field rules:

- `error`: `null`, or `"invalid_cve_token"` when a `sync CVE-…` token
  fails the CVE-ID validation the skill requires. When `error` is
  non-null, nothing is searched, resolved or dispatched.
- `invalid_tokens`: every selector token that failed CVE-ID
  validation, verbatim as the user typed it. Empty list otherwise.
- `searched_cve_ids`: the CVE IDs the orchestrator would interpolate
  into a `gh search issues` call, in the order the user gave them.
  Empty list when no CVE search runs.
- `resolved`: the concrete tracker numbers the selector resolves to,
  ascending, after every exclusion the skill requires (and before
  pre-flight classification).
- `dispatched`: the tracker numbers that would get a sync subagent
  once the user confirms the echoed list (or, for a confirmation-time
  command, on the next turn), ascending. Covers both `dispatch` and
  `dispatch-urgent` classifications.
- `skipped`: one object per tracker the pre-flight classifier marks
  `skip-noop`, ascending by issue number:
  `{"issue": <N>, "rule": "<enum>"}` where `rule` is one of
  `post_announce_cve_published`, `stale_closed`,
  `all_phases_done_awaiting_closure`, `awaiting_release`,
  `fix_released_awaiting_advisory`. Empty list when nothing is
  skipped.
- `review_ready_push_bucket`: only when the user turn asks how a
  tracker's mechanical `allocated → review-ready` (Vulnogram
  `DRAFT → REVIEW`) state push is confirmed: `"non_cve_affecting"`
  or `"cve_affecting"`, naming the bucket whose confirmation the push
  rides. `null` otherwise.

Do not include any text outside the JSON object.
