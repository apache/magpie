<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 9 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "reproducibility",
  "status": "PASS" | "WARN" | "FAIL" | "SKIP",
  "mandatory": true | false,
  "source": {
    "enabled": true | false,
    "verdict": "identical" | "content-identical" | "differs" | "tag-moved" | null,
    "recorded_commit": "<sha or null>",
    "source_date_epoch": <integer or null>,
    "rule_failures": ["<check name>"],
    "metadata_differences": ["<string>"],
    "content_differences": ["<added/removed/changed path>"]
  },
  "binaries": {
    "mode": "off" | "byte-identical" | "documented-divergence",
    "identical": ["<artefact>"],
    "differs": ["<artefact>"],
    "known_divergences_hit": ["<artefact>: <pattern>"]
  },
  "trusted_hardware_asserted": true | false,
  "paste_recipe": "<multi-line shell commands>"
}
```

Grading rules:
- `source.verdict` echoes the `repro-archive compare` verdict stated in
  the report (`identical`, `content-identical`, `differs`), or
  `tag-moved` when the tag no longer resolves to the recorded commit.
- `status` is `"FAIL"` for `differs` or `tag-moved`, and for any
  binary in `binaries.differs`.
- `content-identical` is `"WARN"` in RM-key mode and `"FAIL"` when the
  report states `automated_release_signing: enabled` (the policy
  requires bit-by-bit identity).
- `mandatory` is `true` only under `automated_release_signing: enabled`;
  `--skip-repro` is then ignored.
- `"SKIP"` only when nothing is enabled or `--skip-repro` applies in
  RM-key mode.
- `trusted_hardware_asserted` mirrors `--trusted-hardware` exactly; it
  is never `true` unless the report says the flag was passed.
- `paste_recipe` must be non-empty whenever `status` is not `"SKIP"`
  and must contain `repro-archive build` and `repro-archive compare`.
- No extra keys are permitted in the response.
