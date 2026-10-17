<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — Step 5b closing comment

Read from [`SKILL.md` Step 5b](../SKILL.md#5b--closing-comment-on-the-tracker); `<sm> render-close` renders it.

Brief, process-shaped. Examples:

```markdown
Closing as `invalid` per team consensus in [this discussion](#issuecomment-<id>).

Reasoning summary in the [status rollup](#issuecomment-<rollup-id>); a draft reply to the reporter is in Gmail awaiting review.
```

For PR-imported trackers, replace *"a draft reply to the reporter
is in Gmail awaiting review"* with *"no reporter notification
(PR-imported tracker — see the import-from-pr skill's
[Reporter credit policy](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import-from-pr/SKILL.md#reporter-credit-policy-for-public-pr-imports))"*.

The comment links must resolve once the rollup entry from Step 5e
has been posted (capture its URL and substitute before posting
this closing comment, or post the rollup first and use its ID
here).
