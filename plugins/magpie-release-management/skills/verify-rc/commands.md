<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Commands

Save the configuration once, then let it write every `release-verify` invocation
(`<framework>` is `.apache-magpie` in an adopting project, `.` in the framework checkout):

```bash
uv run --project <framework>/tools/release-config release-config load \
  --skill verify-rc <version>-rcN > <scratch>/verify-rc-load.json
uv run --project <framework>/tools/release-management release-management verify-rc args \
  --load <scratch>/verify-rc-load.json --staging-copy <staging-copy> --keys-file <keys-file> \
  [--previous-dir <previous-dir>]
```

`commands` holds one resolved [`release-verify`](../../../../tools/release-verify/README.md) command per step (`all` runs Steps 1–3 and 5–8 at once),
built from `§ Expected artefact list` (`--expect` / `--expect-optional` by its `required` / `optional` marking, in order),
`§ Digest set`, `§ Binary-exclude list`, `§ Source-tree validators` and `version_manifest_files`.
`args` adds `--podling` by itself when `project_stage` in `release-management-config.md` is `incubating`:
read the stage from that key or from `args`' own `project_stage` (never from a disclaimer file —
the missing file is what the podling check must detect), and carry its `podling` value into the report.
When the key is unset for an ASF project, `args` warns and no disclaimer check runs:
ask the RM once whether the project is incubating (as `committer-onboarding` asks for organization facts),
record `project_stage: incubating` or `top-level` in `<project-config>/release-management-config.md`,
and re-run `release-config load` — the stage is a config fact, not a per-RC decision.
Run them as printed; surface `warnings`.

`<verify-rc>` below is `uv run --project <framework>/tools/release-management release-management verify-rc <command> --load <scratch>/verify-rc-load.json`:
it reads files you saved, prints JSON, and runs nothing.
`status: null` with `pending` is never a result: supply what `pending` names.
Surface `notes`, `skip_reason` and `warning` in the report, not in a step's returned JSON.
