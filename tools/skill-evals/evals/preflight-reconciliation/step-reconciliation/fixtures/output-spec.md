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
  (`acknowledged.sweep` matches).
- `"propose_config"` — the hash differs and a `requires_config` entry no
  longer resolves through the lookup chain.
- `"propose_reanchor"` — the hash differs, every `requires_config` entry
  still resolves, so a structural anchor moved instead.
- `"propose_sweep"` — neither the committed lock nor the local file names
  this skill in a `skills:` map: no baseline to diff against, whether
  because no `reconciled:` block exists anywhere or because one exists but
  never covered this skill.

`changed` names what moved: `["requires_config"]`, `["anchors"]`, both
together when both apply, or `["no_stamp"]` for the sweep case; empty when
`outcome` is `"silent"`.

Do not include any text outside the JSON object.
