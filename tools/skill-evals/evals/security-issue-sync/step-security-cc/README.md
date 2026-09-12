<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security draft CC regression

Covers [apache/magpie#181](https://github.com/apache/magpie/issues/181).
The fixture extracts the shared mail-source contract live, so the same
recipient rule is exercised for all four security drafting workflows.

Thirteen cases cover a configured list, whitespace-only configuration,
a missing key with the ASF fallback, an unfilled template, no usable
address, a non-ASF fallback, trimming and CC deduplication, and resetting
a fallback left by an earlier run. Five cases supply separate project,
organization and framework-default layers, including an explicit null
override, to exercise precedence before recipient selection. List-search assertions ensure a draft
fallback is not reused for mailbox discovery.

Run from the repository root:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
  tools/skill-evals/evals/security-issue-sync/step-security-cc/
```

Print mode assembles prompts only; use `--cli` for an automated model run.
