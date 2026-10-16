<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b — Emit reproducibility self-check commands (optional)

Run **after** the build and **before** signing:
a non-reproducible build found here costs a rebuild, found by a voter it costs an RC.

```bash
uv run --project <framework>/tools/release-management release-management rc-cut render \
  --step 2b --load <scratch>/rc-cut-load.json --upstream <upstream> --project <project> \
  --framework <framework> --epoch "<SOURCE_DATE_EPOCH from Step 2>" [--skip-repro-check]
```

The render decides whether the check runs:
skipped when `reproducibility_source` is `off` and no convenience artefact resolves to a mode other than `off` (its own `reproducibility`, else `reproducibility_binaries`), or on `--skip-repro-check` under `rm-key`;
mandatory, with the flag ignored, under `ci-automated`.

When it runs, every build command runs in a fresh checkout of the RC tag, never in an empty directory:
`rebuild_tree_commands` add a detached worktree of `<version>-<rcN>` at `rebuild/src`, and `cleanup_commands` remove it once the outcome is recorded.
`source_check_commands` lint the artefact against the reproducible-builds.org checklist, rebuild it from the same tag and require byte-identical output:
under `git-archive`, `repro-archive build` reads the tag itself and writes `rebuild/<artefact>`;
under `custom`, `build_command` runs in `rebuild/src`.
Build blocks preserve inline comments and heredocs, and stop if the rebuild checkout cannot be entered.
`binary_check_commands` run each convenience artefact's `build_command` in `rebuild/src`, with `<version>` rendered as that artefact's own `version`, and compare by its `reproducibility` mode
(`byte-identical` compares bytes, `documented-divergence` runs its `verification_command`, by default `diffoscope`); an `off` artefact gets no command, only a `SKIP` line in `text`.

`binary_check_modes` reports each artefact's effective mode; `binary_check_mode` reports the active mode, `mixed` when active modes differ, or `off` when no binary check runs.

The comparisons assume what Step 2 assumes: a build command writes each artefact into the directory it runs in, under the name `expected_artefacts` or the entry's `name` gives it.
The staged copy is then `<artefact>` at the checkout root and the rebuilt one `rebuild/src/<artefact>`.
A build that writes elsewhere (a `dist/` or `target/` directory) needs a `verification_command` naming both paths.

Present `text`; the RM runs it and reports the outcome.
On any `differs` / `DIFFERS`, read [`classifications/self-check-failed.md`](classifications/self-check-failed.md): it stops the cut before anything is signed.

Return ONLY valid JSON with this structure (the render's fields):

```json
{
  "source_check_enabled": true | false,
  "binary_check_mode": "off" | "byte-identical" | "documented-divergence" | "mixed",
  "binary_check_modes": {"<artefact>": "off" | "byte-identical" | "documented-divergence"},
  "mandatory": true | false,
  "rebuild_tree_commands": ["mkdir -p rebuild", "<worktree add of the RC tag at rebuild/src>"],
  "source_check_commands": ["<repro-archive check …>", "<rebuild from the tag>", "<repro-archive compare --require-identical …>"],
  "binary_check_commands": ["<command>"],
  "cleanup_commands": ["<worktree remove rebuild/src>"],
  "stop_on": ["differs", "DIFFERS"],
  "proposed": true
}
```
