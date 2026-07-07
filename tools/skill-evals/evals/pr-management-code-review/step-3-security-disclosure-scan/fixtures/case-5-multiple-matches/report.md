<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Fix privilege escalation in task instance API

Body:
An authenticated user could exploit a missing authorisation check to
escalate privileges via the task instance endpoint.

Commit messages:
- "Add authorisation check to task instance API"
