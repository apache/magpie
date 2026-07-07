<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **newsfragment** sub-step of `security-issue-fix`.

A fix scenario is provided. Return the newsfragment decision.

```json
{
  "include_newsfragment": true | false,
  "rationale": "<one sentence>",
  "security_framing_violation": true | false
}
```

Field rules:
- `include_newsfragment`: default is `false` — security-adjacent bug fixes do not add a newsfragment in the initial PR; reviewers ask for one if needed.
- `security_framing_violation`: `true` if a proposed newsfragment text describes the change as a security fix (reveals the security nature). Should be `false` in all correct outputs.
