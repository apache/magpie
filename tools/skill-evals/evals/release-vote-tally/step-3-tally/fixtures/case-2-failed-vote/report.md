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
    - from: carol@example.com        binding: true  value: -1
    - from: frank@gmail.com          binding: false value: +1
    - from: grace@outlook.com        binding: false value: +1
  ambiguous: []

Pass rule: ASF baseline — binding_plus1 >= 3 AND binding_plus1 > binding_minus1
Counts: binding +1 = 2, binding -1 = 1 → FAILED (2 < 3 minimum binding +1)

Output of `python3 <skill-dir>/scripts/tally.py --votes votes.json --roster projects/airflow/pmc-roster.md` (votes.json holds only from / date / value):

```json
{
  "mechanism": "dev-list-vote",
  "voters": [
    {
      "from": "alice@apache.org",
      "date": null,
      "value": "+1",
      "binding": true,
      "matched_by": "primary_email",
      "on_roster": true
    },
    {
      "from": "bob.martinez@apache.org",
      "date": null,
      "value": "+1",
      "binding": true,
      "matched_by": "primary_email",
      "on_roster": true
    },
    {
      "from": "carol@example.com",
      "date": null,
      "value": "-1",
      "binding": true,
      "matched_by": "primary_email",
      "on_roster": true
    },
    {
      "from": "frank@gmail.com",
      "date": null,
      "value": "+1",
      "binding": false,
      "matched_by": null,
      "on_roster": false
    },
    {
      "from": "grace@outlook.com",
      "date": null,
      "value": "+1",
      "binding": false,
      "matched_by": null,
      "on_roster": false
    }
  ],
  "ambiguous": [],
  "halted_on_ambiguous": false,
  "force_close": false,
  "binding_plus1": 2,
  "binding_minus1": 1,
  "binding_zero": 0,
  "nonbinding_plus1": 2,
  "nonbinding_minus1": 0,
  "nonbinding_zero": 0,
  "fractional_count": 0,
  "excluded_ambiguous_count": 0,
  "pass_rule_applied": "ASF baseline: binding_plus1 >= 3 AND binding_plus1 > binding_minus1",
  "override_errors": [],
  "result": "FAILED",
  "proposed_label": "rc-rolled"
}
```
