<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — the detect loop

From Step 1, as the skill carried it; `security-management issue-import-via-forwarder detect` runs it.

Iterate the registered adapters in the order they appear under
`forwarders.enabled`:

```text
for adapter in forwarders.enabled:
    result = adapter.detect(message)
    if result is not None:
        matched_adapter = result
        break
else:
    matched_adapter = None
```

The detect contract is in [`tools/forwarder-relay/README.md` § `detect()`](../../../../../tools/forwarder-relay/README.md#detectmessage---adapter_name--null): each adapter evaluates the AND of a *sender-pattern* check against `From:` and a *preamble-match* regex against the first ~400 characters of the body; one signal alone is not a relay and is reported under `partial_matches` for the user to see.
The first non-null wins; later adapters are skipped.

**When `matched_adapter is None`** — no registered adapter recognised the message.
Return immediately with `match: null, sub_skill_applied: false` and the note *"no registered forwarder adapter matched this message; parent skill proceeds with the direct-reporter path"*.
The parent keeps its direct-reporter classification for this candidate.
Do **not** fall back to a guess.

**When `matched_adapter` is set** — record:

- the adapter's `name` (for the recap);
- the matched preamble snippet (the first ~80 characters of the body that matched the adapter's `preamble_match`) — surfaced verbatim in the parent's proposal as a one-line *"yes this looks right"* check for the reviewer;
- the matched sender pattern;

and continue to Step 2.
