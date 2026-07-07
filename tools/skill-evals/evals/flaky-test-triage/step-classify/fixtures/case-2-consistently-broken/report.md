<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Job: "integration-tests / database"
Window: 30 days
Total runs: 20
  - success: 2
  - failure: 18
  - cancelled: 0
Re-run recovery: 0 instances where a later attempt succeeded after a failure on the same SHA.
Failure rate: 18/20 = 0.90
