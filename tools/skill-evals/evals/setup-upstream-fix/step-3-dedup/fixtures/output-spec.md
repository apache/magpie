<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "match": "none" | "open-issue" | "open-pr" | "merged-fix",
  "action": "propose-new-pr" | "inform-open-issue" | "inform-open-pr" | "propose-upgrade",
  "reason": "<one-sentence explanation>"
}
```

`match` → `action` mapping:
- `none` (no existing issue or PR covers this defect) → `propose-new-pr`.
- `open-issue` (an open issue reports it, no fix yet) → `inform-open-issue` (do not duplicate; may draft a "hit this too" comment).
- `open-pr` (an open PR already fixes it) → `inform-open-pr` (do not open a second PR).
- `merged-fix` (a PR already merged, or an issue closed as fixed) → `propose-upgrade` (pull it in, do not re-fix).

A borderline "is this the same bug?" match is a question for the user, not an automatic dedup. Do not include any text outside the JSON object.
