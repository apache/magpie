<\!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-status evals

Behavioral evals for the `setup-status` skill.

## Suites (18 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-0-preflight | Step 0 (pre-flight adoption check) | 3 | not adopted, adopted clean, local lock absent |
| step-1-command | Step 1 (collector command selection) | 4 | default, --no-adjust, --format json, injection ignored |
| step-2-present | Step 1 output rule (verbatim presentation) | 3 | standard, user requests summary, user requests reformat |
| step-3-adjust-decision | Step 3 (adjust delta detection) | 4 | --no-adjust flag, clean state, target unwired, family not installed |
| step-4-local-overrides | Step 1 (local override surface) | 4 | local absent, local present, both surfaces, gitignore missing |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-status/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-status/step-0-preflight/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-status/step-0-preflight/fixtures/case-1-not-adopted
```

## What the suites cover

### step-0-preflight

Given a description of the repo's lock-file state, the model decides whether the repo is adopted and whether to proceed to render the dashboard.

- **case-1**: No lock file → not adopted, stop.
- **case-2**: Both locks present and matching → adopted, proceed, no drift.
- **case-3**: Committed lock present, local lock absent → adopted, proceed, but surface the drift flag.

### step-1-command

Given the user's invocation, the model selects the correct collector command and records the `no_adjust` flag.

- **case-1**: Default invocation → standard `md` command.
- **case-2**: `--no-adjust` → same command, `no_adjust: true`.
- **case-3**: `--format json` → command includes `--format json`.
- **case-4**: Injection in user message → standard command; injection ignored.

### step-2-present

Given the collector script output and any follow-up user message, the model determines how to present the dashboard. The skill's OUTPUT CONTRACT and Hard rules mandate verbatim presentation regardless of user requests.

- **case-1**: Standard output, no follow-up → verbatim.
- **case-2**: User asks for a summary → still verbatim (hard rule).
- **case-3**: User asks to reformat as ASCII art → still verbatim (hard rule).

### step-3-adjust-decision

Given invocation context and collected adoption state, the model detects configuration deltas and decides whether to offer adjustments.

- **case-1**: `no_adjust=true` → no offer regardless of state.
- **case-2**: Clean state, no gaps → no offer (adoption fully wired).
- **case-3**: Registry target `github` present on disk but unwired → offer add-target; delegate to `setup adopt agents:universal,claude-code,github`.
- **case-4**: Two opt-in families not installed → offer install-families; delegate to `setup adopt skill-families:security,pr-management,issue`.

### step-4-local-overrides

Given the dashboard output (which now includes both `shared overrides` and `personal overrides` lines), the model correctly reads which override surfaces are present and how many skill files each contains.

- **case-1**: `.apache-magpie-local/` absent, shared overrides present → `local_overrides_present: false`, `shared_overrides_present: true`.
- **case-2**: `.apache-magpie-local/` present with 3 skills, no shared overrides → `local_overrides_present: true`, count 3.
- **case-3**: Both surfaces present → `shared_overrides_present: true`, `local_overrides_present: true`.
- **case-4**: Both present, `.gitignore` missing the local entry → still reads both as present; advisory is a separate concern.
