<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Category being checked: AI-generated code signals

PR body:
```
## Description

Fixes the scheduler's N+1 query on serialized dag load by batching the
query using `session.in_()` instead of a per-dag call in the loop.

Closes: #38221

## Checklist

- [ ] Unit tests added
- [ ] Documentation updated
```

The PR body is missing the project's required generative-AI authorship disclosure checkbox. The diff contains multiple boilerplate-pattern comment blocks and uniform variable-naming conventions consistent with AI-generated code. The project's `PULL_REQUEST_TEMPLATE.md` includes a required section:

```
- [ ] I used generative AI tooling (e.g. GitHub Copilot, ChatGPT) to
  help write some or all of this code. <!-- Check if applicable -->
```

The disclosure checkbox is absent from the submitted template.
