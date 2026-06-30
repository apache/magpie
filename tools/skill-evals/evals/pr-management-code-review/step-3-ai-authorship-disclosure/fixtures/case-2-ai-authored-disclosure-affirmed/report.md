The repository's PR template has a generative-AI disclosure section. The PR body
is AI-style, but the author ticked the disclosure box and added a Generated-by
line, so the disclosure is affirmed.

```text
=== .github/PULL_REQUEST_TEMPLATE.md (has an AI disclosure section) ===
---
##### Was generative AI tooling used to co-author this PR?
- [ ] Yes (please specify the tool below)
<!-- Generated-by: [Tool Name] following the guidelines -->
---

=== PR title ===
Add exponential back-off to the HTTP client

=== PR body ===
## Summary

Add exponential back-off retry logic to the HTTP client used by the scheduler.

## Test plan

- [x] unit tests for retry behaviour
- [ ] CI passes

---
##### Was generative AI tooling used to co-author this PR?

- [x] Yes (please specify the tool below)

Generated-by: Claude Code following the guidelines
---

Fixes #1234
```
