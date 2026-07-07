<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **backport label** sub-step of `security-issue-fix`.

The tracker milestone is provided. Determine which backport label(s) the PR should carry.

```json
{
  "milestone": "<string>",
  "backport_needed": true | false,
  "backport_labels": ["<string>"],
  "rationale": "<one sentence>"
}
```

Field rules:
- `backport_needed`: `true` when the milestone is a patch release branch that exists alongside `main` (e.g. `Airflow 3.2.2`). `false` when the milestone is the next `main`-branch release.
- `backport_labels`: list of `backport-to-vX-Y-test` labels. Empty when `backport_needed` is `false`.
