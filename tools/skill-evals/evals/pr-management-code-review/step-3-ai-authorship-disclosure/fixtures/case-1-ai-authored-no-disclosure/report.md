<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repository's PR template has a generative-AI disclosure section. The PR body
replaces the template with AI-style structure and never affirms the disclosure.

```text
=== .github/PULL_REQUEST_TEMPLATE.md (has an AI disclosure section) ===
---
##### Was generative AI tooling used to co-author this PR?
- [ ] Yes (please specify the tool below)
<!-- Generated-by: [Tool Name] following the guidelines -->
---

=== PR title ===
Clarify custom-time parameterized timetable logic

=== PR body ===
**Title:** Clarify custom-time parameterized timetable logic

## Summary

Clarify the parameterized timetable example so users compare the candidate
time against their custom schedule_at value.

## Changes

- **docs/howto/timetable.rst** -- add a short note explaining the same-day
  versus next-workday boundary for parameterized run times.

## Test plan

- [x] git diff --check
- [x] prek run --stage pre-commit
- [ ] CI passes

Fixes #34897
```
