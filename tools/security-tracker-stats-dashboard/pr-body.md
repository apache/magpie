<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Summary](#summary)
- [Known gap — validation command flag](#known-gap--validation-command-flag)
- [Test plan](#test-plan)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Summary

- Extracts pure helper functions from `render.py` into `_render_helpers.py`
  (YAML parser, `deep_merge`, `parse_dt`, bucket functions, `eval_predicate`,
  `is_bot_body`, JS serialisers) so they can be imported and tested without
  triggering `render.py`'s file-I/O module-level code.
- Adds `pyproject.toml` + `uv.lock` to give the tool a proper uv project
  (dependency-only; `tool.uv.package = false` — no wheel).
- Ships `tests/`: 78 unit tests for the helper functions and 12 integration
  tests that run `render.py` end-to-end against fixture cache data in
  `tests/fixtures/`.

Closes spec acceptance criterion #3 ("the tool ships its own tests").

## Known gap — validation command flag

The implementation plan's validation command reads:

```bash
uv run --project tools/security-tracker-stats-dashboard --group dev pytest
```

`--project` does not change CWD, so pytest discovers all test files in the
repo root instead of just this tool's `tests/`. The correct invocation is:

```bash
uv run --directory tools/security-tracker-stats-dashboard --group dev pytest
```

(This is the same issue that affects `spec-status-index` and other tools.)
A plan/update beat should correct the validation command in the spec.

## Test plan

- [x] `bash -n tools/security-tracker-stats-dashboard/run.sh` — passes
- [x] `uv run --directory tools/security-tracker-stats-dashboard --group dev pytest` — 90 passed
- [x] Pre-commit hooks (typos, trailing-whitespace, placeholders) — all passed
