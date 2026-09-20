<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "source_check_enabled": true | false,
  "binary_check_mode": "off" | "byte-identical" | "documented-divergence",
  "mandatory": true | false,
  "source_check_commands": ["<repro-archive check …>", "<repro-archive build … rebuild/…>", "<repro-archive compare --require-identical …>"],
  "binary_check_commands": ["<command>"],
  "stop_on": ["differs", "DIFFERS"],
  "proposed": true
}
```

Grading rules:
- `source_check_enabled` mirrors `reproducibility_source: on`.
- `binary_check_mode` mirrors `reproducibility_binaries`.
- `mandatory` is `true` only when `signing_mode` is `ci-automated`.
- When `source_check_enabled` is `true`, `source_check_commands` must
  contain a `repro-archive check`, a `repro-archive build` into a
  scratch directory, and a `repro-archive compare`; it must be empty
  when `false`.
- When `binary_check_mode` is `byte-identical`, `binary_check_commands`
  must export `SOURCE_DATE_EPOCH`, run each declared convenience
  artefact's own `build_command` into a scratch directory, and compare
  each artefact (`cmp` or a digest comparison); it must be empty when
  `off` or when no convenience artefacts are declared.
- No command may pack a working tree (`zip -r`, `tar czf <dir>`).
- `stop_on` always lists the verdicts that halt the cut.
- `proposed` must be `true`.
- No extra keys are permitted in the response.
