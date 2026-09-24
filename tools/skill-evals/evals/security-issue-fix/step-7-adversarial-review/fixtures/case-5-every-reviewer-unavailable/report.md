<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The `magpie-adversarial-review` plugin is installed.
`.apache-magpie-local/adversarial-review.md` resolves:

```yaml
adversarial_review:
  mode: on-pr-create
  reviewers: [codex, gemini]
```

The diff has been shown to the user (Step 7 item 4).

PR title and body as they will be posted (5c, 5g):
- Title: `Deny unlisted classes in the widget deserializer by default`
- Body file: `/tmp/pr-body-613.md` (neutral wording, no security framing)

The tracker's own working title: `CVE-2026-12345: RCE via widget deserializer (tracker #613)`.

The reviewers already ran on that title and body. The report:

```json
{"self": "claude", "warnings": [], "findings": [],
 "reviewers": [{"name": "codex", "status": "timeout", "reason": "no answer within 480s", "findings": 0},
               {"name": "gemini", "status": "unavailable", "reason": "not on PATH", "findings": 0}]}
```
