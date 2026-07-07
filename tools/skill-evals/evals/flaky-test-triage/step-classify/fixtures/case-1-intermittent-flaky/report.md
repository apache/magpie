<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Job: "unit-tests / python-3.11"
Window: 30 days
Total runs: 50
  - success: 42
  - failure: 8
  - cancelled: 0
Re-run recovery: 5 instances where a later attempt (run_attempt >= 2) succeeded after attempt 1 failed on the same SHA.
Failure rate: 8/50 = 0.16
