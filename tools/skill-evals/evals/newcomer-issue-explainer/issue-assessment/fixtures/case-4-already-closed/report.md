<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #301

State: closed
Labels: good first issue
Title: Add `--dry-run` flag to the `deploy` command
Body:
The `deploy` command should support a `--dry-run` mode that prints the
actions it would take without executing them.

Relevant file: `src/acme/cli/deploy.py`
Acceptance criteria: `deploy --dry-run` prints actions without executing;
`deploy` (no flag) behaves as before; a test covers both modes.

(This issue was closed when the feature was merged in PR #312.)
