<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
RC identifier: 2.11.0-rc2
mechanism: dev-list-vote
result_subject_template: "[RESULT] [VOTE] Release Apache Airflow <version> from <version>-<rcN>"
vote_list: dev@airflow.apache.org
--force-close: not passed
vote_pass_rule_overrides: none

Classifications from Step 2:
  classifications:
    - from: alice@apache.org         binding: true  value: +1
    - from: bob.martinez@apache.org  binding: true  value: +1
    - from: carol@example.com        binding: true  value: +1
    - from: frank@gmail.com          binding: false value: +1
    - from: grace@outlook.com        binding: false value: +1
  ambiguous: []

Pass rule: ASF baseline — binding_plus1 >= 3 AND binding_plus1 > binding_minus1
Counts: binding +1 = 3, binding -1 = 0 → PASSED (3 >= 3 and 3 > 0)
