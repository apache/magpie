<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add retry logic to the HTTP client

Body:
This PR adds exponential back-off retry logic to the HTTP client used
by the scheduler. Fixes #1234.

Commit messages:
- "Add retry logic to HTTP client with exponential back-off"
- "Add unit tests for retry behaviour"
