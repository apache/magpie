<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `git-branch` (pinned snapshot).

Scope: 3 configured security import skills, no override files.
All three skills' `requires_config:` entries resolve from the personal
layer or committed overrides. All their SKILL.md files are readable.
No anchor or required-configuration findings exist.

Existing vetted-ops policy:
`.apache-magpie-overrides/tools/vetted-ops/config.toml`
The policy is valid TOML and has this `[callers]` section:

```toml
[callers]
"security-issue-import-from-md" = ["issue-view"]
"security-issue-import-from-pr" = ["rollup-append"]
"security-issue-sync" = ["issue-view", "rollup-append"]
```

The following workflows are configured and in scope:

- `security-issue-import` requires `rollup-append`.
- `security-issue-import-from-md` requires `rollup-append`.
- `security-issue-import-from-pr` requires `pr-view-with-body`
  and `rollup-append`.

No one has confirmed changes to the vetted-ops policy.
Do not modify the policy or write a clean reconciliation stamp.
Return the missing caller/grant proposals only.
