<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Security model excerpts (revision 2026-09)

### Capabilities of workflow authors
Workflow authors can execute arbitrary code on workers. Their code must never execute in the scheduler or the API server.

### Authenticated users
Authenticated UI users must not exceed the permissions of their role.

## Statement the maintainer wants in threat_model.md

"Denial of service by an authenticated user (for example a very large API request) is not a vulnerability."
