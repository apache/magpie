<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Security model excerpts (revision 2026-09)

### Capabilities of workflow authors
Workflow authors can execute arbitrary code on workers. Their code must never execute in the scheduler or the API server.

### What is not a vulnerability
Code execution on a worker by a workflow author is expected behaviour.

## Statement the maintainer wants in threat_model.md

"Report code from a workflow file running in the scheduler or the API server; workflow-author code running on a worker is by design."
