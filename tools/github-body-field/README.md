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
    - [`normalise [<issue> | --body-file <path>]`](#normalise-issue----body-file-path)
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

Under the [secure agent setup](../../docs/setup/secure-agent-setup.md) this CLI's `gh` runs sandboxed and fails,
so skills call the same procedures through [`vetted-ops`](../vetted-ops/README.md#tracker-procedures-rollup-and-body-field-writes) instead:
`vetted-op-tracker --caller <skill> body-field-set <N> "<field>" <scratch>/value.md` to write,
`vetted-op-read --caller <skill> body-field-get <N> "<field>"` to read.
The uv CLI remains for use outside the sandbox.

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

### `normalise [<issue> | --body-file <path>]`

Report the canonical form of a body — the shape every field reader agrees on — without pushing anything.
The JSON on stdout carries `changes` (`{line, kind}` per rewrite, input line numbers), `needs_decision` (`{field, kind: "duplicate", lines}` per field the tool will not choose for you) and `changed`; it never carries body text.

- `--fields-json <path>`: a JSON array of the template's field names; a heading equal to one once case-folded and whitespace-collapsed takes its spelling.
- `--keep "<field>=<line>"` (repeatable): resolve a duplicate by keeping the copy whose heading is on that line — a decision a human made.
- `--output <path>`: write the normalised body to a local file, for a confirmed whole-body rewrite (`gh issue edit <N> --body-file <path>`).

What it rewrites: `\r\n` and `\r` to `\n` (`line_endings`);
a level-3 heading to `### Name` (`heading`, `heading_name`);
a heading-shaped line inside a fence to `\###` (`heading_in_fence`);
a fence left open at the end to a closed one (`unclosed_fence`);
a repeated field whose copies hold the same value to its first copy (`duplicate_dropped`, or `duplicate_resolved` with `--keep`).
Copies with different values stay as they are and land in `needs_decision`.
A heading-shaped line that is not a field heading is never rewritten;
when it names a known field (after stripping `>` and list markers), `{field, kind: "container-heading", lines}` lands in `needs_decision`, never taken as the field and never ignored.
After normalising, a strict reader (`### <name>` at column 0, fences opened only at column 0, fence content unescaped) cross-checks the result,
and a field heading the two disagree on lands there too, instead of either reading winning.
The same function is importable as `github_body_field.normalise(body, known_fields, keep)`; `generate-cve-json` calls it in memory before every read.

## Body format assumptions

The parser follows CommonMark where it matters for finding fields:

- lines end at `\n`, `\r\n` or `\r` — not at the other characters `str.splitlines` breaks on;
- a field heading is a level-3 ATX heading outside any fence: up to three spaces of indent, `###`, spaces or tabs, the name, an optional closing run of `#`;
  level-2 and level-4 headings are content;
- lists and block quotes are deliberately not modelled, so the rule fails closed:
  a field heading is a `### <name>` line at column 0, or a lenient one (extra spaces or tabs after `###`, closing `#`s) at column 0 after a blank line or a field heading,
  or an indented one only right after a field heading or as the first line;
  any other heading-shaped line (behind `>` or a list marker, indented, under paragraph text) is never a field;
- fenced code blocks pair the CommonMark way: the closer uses the opener's character (`` ` `` or `~`), is at least as long, and has nothing but whitespace after the run;
  an unclosed fence runs to the end of the body.
  So a four-backtick block holding a three-backtick line keeps its content,
  and a literal `### foo` inside a shell snippet never false-matches as a heading;
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
| 2 | CLI argument error (e.g. both `--value` and `--value-file` given), or `get` / `set` refused an ambiguous field (`AmbiguousFieldError`): the strict cross-check finds a different field set, or a heading naming the field sits behind `>`, a list marker or an indent. Every read and write runs this check itself; the body is untouched. |
| 3 | Field heading not found, or matched more than once (`DuplicateFieldError`, a `FieldNotFoundError`). The body is untouched. |
| other | `gh` returned non-zero; the underlying `gh` stderr is forwarded. |
