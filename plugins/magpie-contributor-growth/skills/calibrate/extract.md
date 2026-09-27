<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Extract

One row per nomination, built from its `[DISCUSS]`, `[VOTE]` and `[RESULT]` threads on `<private-list>`.

## Row

```json
{
  "thread_id": "<id of the thread the row was built from — the [VOTE] thread when there is one>",
  "nominee_name": "<as written in the thread>",
  "handle": "<GitHub handle, or null until Step 2 resolves it>",
  "target": "committer | pmc",
  "vote_date": "YYYY-MM-DD",
  "outcome": "elected | deferred | withdrawn",
  "deferral_category": "narrow-focus | little-list-presence | short-tenure | other | null"
}
```

## Rules

- **Outcome.**
  `elected` when a `[RESULT]` message or the vote tally shows the vote passed.
  `deferred` when the discussion ends without a vote after objections or a "not yet", or a vote fails.
  `withdrawn` when the nominator withdraws the nomination.
- **Vote date.** The date of the `[RESULT]` message, else the close of the vote, else the last message of the discussion.
- **Target.** `pmc` when the nomination is for the `<governance-body>`, else `committer`.
- **Deferral category**, only for `deferred`, from the reasons given:
  - `narrow-focus` — work confined to one area, one component, or one vendor's integrations;
  - `little-list-presence` — rarely seen on the development list, in release testing, or in discussion;
  - `short-tenure` — sustained activity too recent or too short;
  - `other` — any other reason, or reasons too unclear to place.
  `null` for `elected` and `withdrawn`.

## What a row never contains

- who said what, who objected, or who supported;
- how many votes were cast or by whom;
- any quote from the thread;
- anything about a nominee beyond the fields above.

The row is the only thing the skill takes from the thread.
