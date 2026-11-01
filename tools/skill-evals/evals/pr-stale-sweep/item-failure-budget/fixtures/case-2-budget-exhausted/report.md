<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The pool has 10 PRs: 101 to 110. `pr-management-config.md` leaves `item_failure_budget` unset.
While reading and classifying, PRs 102, 103 and 105 each had a missing body, and PR 107
has just failed too: its saved read is malformed JSON. Prs 101, 104 and 106 classified
normally; 108 to 110 have not been read yet. No write has happened.
