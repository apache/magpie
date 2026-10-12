<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b — Emit reproducibility self-check commands (optional)

Run **after** the build and **before** signing:
a non-reproducible build found here costs a rebuild, found by a voter it costs an RC.

```bash
uv run --project <framework>/tools/release-management release-management rc-cut render \
  --step 2b --load <scratch>/rc-cut-load.json --upstream <upstream> --project <project> \
  --epoch "<SOURCE_DATE_EPOCH from Step 2>" [--skip-repro-check]
```

The render decides whether the check runs:
skipped when `reproducibility_source` and `reproducibility_binaries` are both `off`, or on `--skip-repro-check` under `rm-key`;
mandatory, with the flag ignored, under `ci-automated`.
When it runs, `source_check_commands` lint the artefact against the reproducible-builds.org checklist, rebuild it from the same tag into `rebuild/` and require byte-identical output;
`binary_check_commands` rebuild each convenience artefact by its `reproducibility` mode (`byte-identical` compares bytes, `documented-divergence` runs its `verification_command`, `off` prints `SKIP`).

Present `text`; the RM runs it and reports the outcome.
On any `differs` / `DIFFERS`, read [`classifications/self-check-failed.md`](classifications/self-check-failed.md): it stops the cut before anything is signed.

Return ONLY valid JSON with this structure (the render's fields):

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
