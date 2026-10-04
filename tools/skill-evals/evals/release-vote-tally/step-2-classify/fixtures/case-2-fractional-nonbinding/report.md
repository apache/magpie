<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (no overrides)
RC identifier: 2.11.0-rc2
mechanism: dev-list-vote
roster_path: projects/airflow/pmc-roster.md

Roster (projects/airflow/pmc-roster.md):
  Apache ID | Name            | Primary email              | Binding since
  alice     | Alice Nguyen    | alice@apache.org           | 2021-03-15
  bob       | Bob Martínez    | bob.martinez@apache.org    | 2020-11-01
  carol     | Carol Singh     | carol@example.com          | 2022-08-20

Raw approval records from Step 1 (dev-list-vote thread):
  1. from: alice@apache.org         date: 2026-06-11T09:00:00Z  raw_vote_line: "+1"         parsed_value: +1
  2. from: bob.martinez@apache.org  date: 2026-06-11T11:30:00Z  raw_vote_line: "+1"         parsed_value: +1
  3. from: carol@example.com        date: 2026-06-12T14:00:00Z  raw_vote_line: "+0.9"       parsed_value: fractional
  4. from: dave@contributor.io      date: 2026-06-12T16:00:00Z  raw_vote_line: "+1"         parsed_value: +1

Note: carol@example.com is on the roster (binding member), but cast a fractional vote (+0.9).
Per golden rule 4, fractional votes are non-binding regardless of roster membership.

Output of `python3 <skill-dir>/scripts/tally.py --votes votes.json --roster projects/airflow/pmc-roster.md` (votes.json holds only from / date / value):

```json
{
  "mechanism": "dev-list-vote",
  "voters": [
    {
      "from": "alice@apache.org",
      "date": "2026-06-11T09:00:00Z",
      "value": "+1",
      "binding": true,
      "matched_by": "primary_email",
      "on_roster": true
    },
    {
      "from": "bob.martinez@apache.org",
      "date": "2026-06-11T11:30:00Z",
      "value": "+1",
      "binding": true,
      "matched_by": "primary_email",
      "on_roster": true
    },
    {
      "from": "carol@example.com",
      "date": "2026-06-12T14:00:00Z",
      "value": "fractional",
      "binding": false,
      "matched_by": null,
      "on_roster": true
    },
    {
      "from": "dave@contributor.io",
      "date": "2026-06-12T16:00:00Z",
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
  "binding_minus1": 0,
  "binding_zero": 0,
  "nonbinding_plus1": 1,
  "nonbinding_minus1": 0,
  "nonbinding_zero": 0,
  "fractional_count": 1,
  "excluded_ambiguous_count": 0,
  "pass_rule_applied": "ASF baseline: binding_plus1 >= 3 AND binding_plus1 > binding_minus1",
  "override_errors": [],
  "result": "FAILED",
  "proposed_label": "rc-rolled"
}
```
