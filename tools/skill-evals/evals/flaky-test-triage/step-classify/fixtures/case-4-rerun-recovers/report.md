<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Job: "e2e-tests / chrome"
Window: 30 days
Total runs: 40
  - success: 33
  - failure: 7
  - cancelled: 0
Re-run recovery: 7 instances where a later attempt succeeded after the first attempt failed on the same SHA (all failures recovered on re-run).
Failure rate: 7/40 = 0.175
