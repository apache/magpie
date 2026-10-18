<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-welcome-guide evals

Behavioural evals for the `setup-welcome-guide` skill (`/magpie-setup:welcome-guide`).

## Suites (3 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-1-show | Step 1 (resolve the guide, run the command, present it) | 3 | no argument (general guide), a known family, an unknown family (list the guides that ship) |

## Run

```bash
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-welcome-guide/
```

## What the suite covers

Given the user's invocation and what the checker printed, the model names the guide,
the command it ran, and what it shows.

- **case-1**: No argument → `general`, shown verbatim.
- **case-2**: *"show the security guide"* → `security`, shown verbatim.
- **case-3**: An unknown name → the command exits 2; list the guides that ship, invent none.

None of the cases asks for a guide back, so `enable` is `false` in all three:
showing a guide never clears its recorded choice.
