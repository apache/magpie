<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b — Emit reproducibility self-check commands (optional)

Skipped when `reproducibility_source` is `off` **and** `reproducibility_binaries` is `off`,
or when `--skip-repro-check` was passed and `signing_mode` is `rm-key`.
Mandatory (the flag is ignored) when `signing_mode` is `ci-automated`.
Run **after** the build and **before** signing:
a non-reproducible build found here costs a rebuild, found by a voter it costs an RC.

**Source (`reproducibility_source: on`).**
Lint the artefact against the reproducible-builds.org checklist, rebuild it into a scratch directory from the same tag, and compare:

```text
# 1. every archive rule holds (single SOURCE_DATE_EPOCH mtime, sorted, uid/gid 0, a=rX,u+w, no PAX atime/ctime, gzip -n / zip -X)
uv run --project <framework>/tools/reproducible-archive repro-archive check \
  "<source-artefact-filename>" --epoch "<SOURCE_DATE_EPOCH>"
# 2. rebuild from the tag and require byte-identical output
mkdir -p rebuild
uv run --project <framework>/tools/reproducible-archive repro-archive build \
  --ref "<version>-<rcN>" --format <source_archive_format> \
  --prefix "<source_archive_prefix>" -o "rebuild/<source-artefact-filename>"
uv run --project <framework>/tools/reproducible-archive repro-archive compare --require-identical \
  "<source-artefact-filename>" "rebuild/<source-artefact-filename>"
```

With `source_archive_method: custom` the `check` still runs (it lints any `.tar`, `.tar.gz` or `.zip`);
the rebuild step re-runs `build_command` into `rebuild/` and compares with `repro-archive compare`.
`content-identical` is then a warning to switch the build to `repro-archive build` or `repro-archive recipe`;
`differs` is a stop.

**Convenience artefacts.**
One block per entry in `convenience_artefacts`, using the entry's `reproducibility` mode (default `reproducibility_binaries`).
`byte-identical` — re-run the entry's `build_command` into `rebuild/` under the same `SOURCE_DATE_EPOCH` and compare bytes:

```text
export SOURCE_DATE_EPOCH="<SOURCE_DATE_EPOCH>"
( cd rebuild && <artefact.build_command> )
cmp "<artefact.name>" "rebuild/<artefact.name>" \
  && echo "identical: <artefact.name>" || echo "DIFFERS: <artefact.name>"
```

`documented-divergence` — the same rebuild, then the entry's `verification_command` (for example `diffoscope <artefact.name> rebuild/<artefact.name>`);
any difference not listed under the entry's `known_divergences` is a stop, listed ones are reported.
`off` — state `SKIP` explicitly for that artefact.
An artefact that does not reproduce here is not good to sign:
it is not known to be what the tagged source produces, and `release-promote` will withhold its publication until a verify-rc run reproduces it.

The RM runs the block and reports the outcome.
Any `differs` / `DIFFERS` stops the cut: the RM fixes the build (or documents the divergence) and rebuilds before signing anything.

Return ONLY valid JSON with this structure:

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

`mandatory` is `true` only when `signing_mode` is `ci-automated`.
`source_check_commands` is empty when `source_check_enabled` is `false`;
`binary_check_commands` is empty when `binary_check_mode` is `off`.
`stop_on` always lists the verdicts that halt the cut.
`proposed` is always `true`.
