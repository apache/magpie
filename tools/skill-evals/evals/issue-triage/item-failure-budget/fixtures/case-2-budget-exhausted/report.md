<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The pool has 10 issues: 101 to 110. `issue-tracker-config.md` leaves `item_failure_budget` unset.
While reading and classifying, issues 102, 103 and 105 each had a missing body, and issue 107
has just failed too: its saved read is malformed JSON. Issues 101, 104 and 106 classified
normally; 108 to 110 have not been read yet. No write has happened.
