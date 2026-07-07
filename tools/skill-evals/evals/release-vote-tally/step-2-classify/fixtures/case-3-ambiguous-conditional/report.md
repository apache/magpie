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
  dave      | Dave Kim        | dave.kim@apache.org        | 2019-05-10

Raw approval records from Step 1 (dev-list-vote thread):
  1. from: alice@apache.org         date: 2026-06-11T09:00:00Z  raw_vote_line: "+1"                         parsed_value: +1
  2. from: bob.martinez@apache.org  date: 2026-06-11T11:30:00Z  raw_vote_line: "+1 all looks good"         parsed_value: +1
  3. from: carol@example.com        date: 2026-06-12T14:00:00Z  raw_vote_line: "+1 if the CI run passes"   parsed_value: AMBIGUOUS
  4. from: dave.kim@apache.org      date: 2026-06-12T16:00:00Z  raw_vote_line: "+1 (binding)"              parsed_value: +1

Note: carol@example.com cast "+1 if the CI run passes" — this is conditional and must be classified
AMBIGUOUS. Do NOT count it in the tally.
--force-close was NOT passed.
