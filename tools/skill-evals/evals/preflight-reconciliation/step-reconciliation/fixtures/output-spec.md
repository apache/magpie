<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{"outcome": "silent | propose_config | propose_reanchor | propose_sweep",
 "changed": ["<what moved, empty when silent>"],
 "update_available": "<version or null>"}
```

`outcome` is the reconciliation-check branch this skill's own pre-flight took:
- `"silent"` — the stamped hash for this skill matches its current
  `surface_hash`, or it differs but was already declined for this exact
  hash (`acknowledged` matches).
- `"propose_config"` — the hash differs and a `requires_config` entry no
  longer resolves through the lookup chain.
- `"propose_reanchor"` — the hash differs, every `requires_config` entry
  still resolves, so a structural anchor moved instead.
- `"propose_sweep"` — there is no baseline to diff against: no
  `reconciled:` block at all, or none covering this skill.

`changed` names what moved: `["requires_config"]`, `["anchors"]`, or
`["no_stamp"]`; empty when `outcome` is `"silent"`.

`update_available` carries the marketplace clone's newer version **only**
when the reconciliation check is not silent and the clone is readable;
otherwise `null`. A silent check never reports an update, even when a
newer version is visible — that piggybacked line only rides on a
reconciliation check that is already speaking.

Do not include any text outside the JSON object.
