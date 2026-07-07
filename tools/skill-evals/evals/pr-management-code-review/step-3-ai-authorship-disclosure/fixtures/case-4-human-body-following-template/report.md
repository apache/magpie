<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repository's PR template has a generative-AI disclosure section. The body is
plain human prose with no AI-authorship signals; the disclosure box is correctly
left unchecked because no AI tooling was used. No finding.

```text
=== .github/PULL_REQUEST_TEMPLATE.md (has an AI disclosure section) ===
---
##### Was generative AI tooling used to co-author this PR?
- [ ] Yes (please specify the tool below)
<!-- Generated-by: [Tool Name] following the guidelines -->
---

=== PR title ===
Fix off-by-one in the workday loop

=== PR body ===
Noticed the workday loop skipped the first eligible day when the start date
landed on a Friday. This walks the loop from the right starting point and adds
a regression test that fails before the fix.

closes: #5678

---
##### Was generative AI tooling used to co-author this PR?

- [ ] Yes (please specify the tool below)
---
```
