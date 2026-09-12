<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification

Resolve the draft's security CC from the supplied trusted configuration.
Return exactly these fields, using null where no address is resolved:

- `security_cc`: resolved address.
- `cc_fallback`: fallback address recorded for this run, or null.
- `warning`: whether a configuration warning must be surfaced.
- `draft_blocked`: whether recipient configuration prevents draft creation.
- `cc`: complete CC array for the proposed draft; empty when blocked.
- `search_list`: trimmed project list address for list searches, or null when unconfigured. This field represents a possible list query, not a mutation to configuration.

Only apply rules present in the supplied contract. Do not invent missing policy.

Emit only the six specified keys. Represent warnings with the `warning` boolean, not additional message fields.
