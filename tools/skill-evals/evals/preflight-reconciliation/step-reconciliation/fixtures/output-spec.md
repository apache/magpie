<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{"outcome": "silent | propose_config | propose_reanchor | propose_sweep",
 "changed": ["<what moved, empty when silent>"]}
```

`outcome` is the reconciliation-check branch this skill's own pre-flight took:
- `"silent"` — the step was skipped entirely (nothing configured or adopted
  yet), or the stamped hash for this skill matches its current
  `surface_hash`, or it differs but was already shown once for this exact
  hash (`acknowledged.skills` matches) or this exact installed version
  (`acknowledged.sweep` matches), or a `reconciled:` block exists in one of
  the two stores but simply does not name this skill.
- `"propose_config"` — the hash differs and a `requires_config` entry no
  longer resolves through the lookup chain.
- `"propose_reanchor"` — the hash differs, every `requires_config` entry
  still resolves, so a structural anchor moved instead.
- `"propose_sweep"` — **no `reconciled:` block exists in either store at
  all**, so this project has never been reconciled and there is no baseline
  for any skill. A stamp that exists but omits this skill is *not* this
  case; it is `"silent"`.

`changed` names what moved: `["requires_config"]`, `["anchors"]`, both
together when both apply, or `["no_stamp"]` for the sweep case; empty when
`outcome` is `"silent"`.

Do not include any text outside the JSON object.
