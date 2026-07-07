<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repository's PR template has NO generative-AI disclosure section — this
project does not ask contributors to disclose AI assistance. The body looks
AI-authored, but there is nothing to enforce, so no finding is raised.

```text
=== .github/PULL_REQUEST_TEMPLATE.md (no AI disclosure section) ===
## Summary

<!-- What changed and why. -->

-

## Checklist

- [ ] Tests added
- [ ] Docs updated

=== PR title ===
Add a retry helper to the storage client

=== PR body ===
**Title:** Add a retry helper to the storage client

## Summary

Adds a small retry helper around the storage client calls.

## Changes

- **storage/client.py** -- wrap calls in a bounded retry.

## Test plan

- [x] unit tests pass
- [ ] CI passes
```
