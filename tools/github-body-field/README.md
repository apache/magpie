<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [github-body-field](#github-body-field)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Why](#why)
  - [Invocation](#invocation)
    - [`get <issue> --field "<name>"`](#get-issue---field-name)
    - [`set <issue> --field "<name>" --value "<v>" | --value-file <path>`](#set-issue---field-name---value-v----value-file-path)
    - [`list <issue>`](#list-issue)
  - [Body format assumptions](#body-format-assumptions)
  - [Failure modes](#failure-modes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# github-body-field

**Capability:** contract:tracker

**Kind:** implementation

**Vendor:** GitHub

Read or rewrite a single `### Field` section of a GitHub issue
body **without bringing the body into agent context**.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (`uv run --directory tools/github-body-field body-field …`); stdlib-only, no third-party dependencies.
- **CLIs:** `uv`; `gh` — the script shells out to it for all GitHub access (the `--repo` argument is forwarded verbatim).
- **Credentials / auth:** an authenticated `gh` session (`gh auth status` must pass) — the body read / parse / replace / push all go through `gh`.
- **Network:** `api.github.com` via `gh`.

## Configuration

This helper has no persistent config file of its own. Callers pass
`--repo <tracker>` from `<project-config>/project.md` and the field names
declared by the adopter's tracker configuration, such as
`<project-config>/issue-tracker-config.md` or sibling
`*-config.md` files that define tracker body fields.

## Why

Tracker issues in `<tracker>` carry a structured body — a list of
`### <FieldName>` sections (e.g. *CVE tool link*, *Reporter
credited as*, *Public advisory URL*, *Short public summary for
publish*). The sync workflow PATCHes one of these fields at a time;
the legacy recipe was *read the full 10–15 KB body into agent
context, regex-edit one field, write it back*. That spent ~5 K
tokens per single-field flip, in addition to looping
reporter-supplied content (often the most sensitive content on
the tracker) through the agent for no reason.

This tool does the read / parse / replace / push in a subprocess.
Only the diff summary lands on the agent's stdout. The body never
crosses the boundary.

## Invocation

```bash
uv run --directory tools/github-body-field body-field --repo <owner>/<repo> <subcommand> ...
```

The `--repo` argument is forwarded verbatim to `gh`; omit it when
the current working directory is already inside the right clone.

### `get <issue> --field "<name>"`

Print the field's value to stdout (with a trailing newline added if
the value did not already end with one — convenient for shell
pipelines). Exit 3 if the field is absent or appears more than once.

### `set <issue> --field "<name>" --value "<v>" | --value-file <path>`

Replace the field's value in place. Either `--value` (single argv
string) or `--value-file` (any path; `-` reads stdin) must be
given. The replacement preserves the original heading line
byte-exact and re-uses the spacer-blank-line convention the original
section had.

`--dry-run` prints the diff summary to stderr but skips the push.

Exit 0 when written (or when the new value matched the old, in
which case stderr says `unchanged: ...` and no API call happens);
exit 3 when the field is absent or duplicated.

### `list <issue>`

Print every field heading present in the body, one per line, in
document order. With `--json`, emit a JSON array instead — useful
when an orchestrator wants to programmatically check what fields a
legacy tracker already has populated.

## Body format assumptions

The parser is a small state machine that:

- treats only top-level `^### <Name>$` lines as field headings;
- tracks fenced code blocks (`` ``` `` and `~~~`) so a literal
  `### foo` inside a shell snippet never false-matches as a
  heading;
- preserves the original body byte-exact when no change is needed
  (idempotent rewrite — a `set` of the same value triggers no
  API write).

If the body does not use the `### <FieldName>` convention at all
(legacy trackers from before the issue template was standardised),
`set` will report `field not found` and refuse to mutate. Fix the
tracker body first or fall through to the original "edit by hand"
path; this tool intentionally does not invent headings.

## Failure modes

| Exit | Meaning |
|---|---|
| 0 | Success (or `set` was a no-op because new value matched current). |
| 2 | CLI argument error (e.g. both `--value` and `--value-file` given). |
| 3 | Field heading not found, or matched more than once. The body is untouched. |
| other | `gh` returned non-zero; the underlying `gh` stderr is forwarded. |
