<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — hand-back schema

## Step 4 — Hand back to parent skill

Return a structured result the parent skill folds into its proposal:

```yaml
sub_skill_applied: true | false
match:
  adapter_name: <string>         # e.g. "asf-security" — recap only
  preamble_snippet: <string>     # first ~80 chars of matched preamble
  sender_pattern_matched: <string>
credit:
  name: <string>                 # empty when adapter returned null
  kind: human | tool | service | unknown
  raw_string: <string>
routing:
  to_recipients: [<string>, ...]
  addressing_block: <string>     # paste-ready, ready to attach to draft
  question_mode: true | false
warnings:
  - <one-line warning>           # e.g. "matched sender is on collaborator list"
notes:
  - <one-line informational>     # e.g. "credit unknown — confirm before draft"
```

When `sub_skill_applied: false`, the other fields are empty / `null`; the parent proceeds with its direct-reporter classification for the candidate.

The parent skill is responsible for:

- folding the `match` block into its proposal so the user sees *"matched as relay via adapter `<name>` — preamble: `<snippet>`"*;
- pre-filling the *Reporter credited as* tracker field with `credit.name` (subject to user override on confirmation);
- assembling the Gmail draft from `routing.to_recipients`, `routing.addressing_block`, and the appropriate canned-response body, using `routing.question_mode` to decide whether to fold the credit-preference question in;
- surfacing every `warning` inline in the proposal — the user decides whether a warning blocks confirmation;
- recording the matched adapter name in the tracker's status-rollup entry per [`tools/github/status-rollup.md`](../../../../tools/github/status-rollup.md), so a future sync pass knows the tracker is in via-forwarder mode without re-detecting.

Hand-back is the only output of this sub-skill: no console recap (the parent's recap includes this sub-skill's contribution), no `gh` call against the tracker, no Gmail draft.
