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

**Capability:** contract:tracker + contract:body-field

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
pipelines). Exit 3 if the field is absent or appears more than once
outside closed code blocks.

### `set <issue> --field "<name>" --value "<v>" | --value-file <path>`

Replace the field's value in place. Either `--value` (single argv
string) or `--value-file` (any path; `-` reads stdin) must be
given. The replacement preserves the original heading line
byte-exact and re-uses the spacer-blank-line convention the original
section had. A value holding a line that would end the field
(`###` at column 0, then a space, a tab or nothing — fenced or not) is refused (exit 2).

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

- `--fields-json <path>`: a JSON array of the template's field names; a heading equal to one once its whitespace is collapsed (case must match, as before) takes its spelling.
- `--keep "<field>=<line>"` (repeatable): resolve a duplicate by keeping the copy whose heading is on that line — a decision a human made.
- `--output <path>`: write the normalised body to a local file, for a confirmed whole-body rewrite (`gh issue edit <N> --body-file <path>`).

What it rewrites: `\r\n` and `\r` to `\n` (`line_endings`);
a fence left open to one closed in the field it opens in (`unclosed_fence`), unless the closer would move a field heading into or out of a closed block;
a field heading outside closed code blocks to `### Name` (`heading`, `heading_name`)
(lines inside a closed block are never rewritten, so fenced payloads round-trip byte-exact);
a repeated field whose copies outside closed blocks hold the same value to its first copy (`duplicate_dropped`, or `duplicate_resolved` with `--keep`).
Copies with different values stay as they are and land in `needs_decision`.
A heading-shaped line that ends no field (behind `>` or a list marker, or indented) is never rewritten;
when it names a known field and sits outside a fence for a CommonMark reader or a column-0-only one, `{field, kind: "container-heading", lines}` lands in `needs_decision`, never taken as the field and never ignored.
A Jira `{code}` / `{noformat}` macro left open mid-line before field boundaries lands there as `{field, kind: "macro-ambiguous", lines}` (the first hidden field; the opener's line, then each hidden heading's).
The same function is importable as `github_body_field.normalise(body, known_fields, keep)`; `generate-cve-json` calls it in memory before every read.

## Body format assumptions

This parser is the one implementation of the body-field contract ([`tools/body-field-contract/contract.md`](../body-field-contract/contract.md)):
every reader and writer of a field, `generate-cve-json` and `vetted-ops` (a byte-identical copy) included, goes through it.

- lines end at `\n`, `\r\n` or `\r` — not at the other characters `str.splitlines` breaks on;
- **every line that starts, at column 0, with `###` followed by a space, a tab or the end of the line ends the current field, code block or not.**
  So no fence, Jira macro or duplicate heading left in one field's text can make it absorb the next field:
  a value is always exactly one section of that split.
  The heading's name drops surrounding spaces and tabs and a closing run of `#`; names compare case-sensitively;
- **a heading inside a closed code block never starts a field**: among the `### <name>` lines, the field is the one outside every closed block, and a field whose only copies are inside closed blocks is absent.
  A closed block is a CommonMark fence pair (the closer uses the opener's character, is at least as long, and has nothing but spaces or tabs after the run;
  a backtick opener whose info string holds a backtick is not a fence),
  or a Jira `{code}` / `{code:…}` / `{noformat}` block opened on a line starting with the macro and closed on the bare macro.
  A block left open at the end marks nothing.
  So a PoC quoting `### Severity` inside a fence is never taken for the field, whether or not the real heading exists,
  and two copies outside closed blocks are a duplicate;
- **a Jira macro a renderer may open mid-line is a decision**: a line outside closed blocks that leaves `{code}` / `{noformat}` open
  (a macro opened and closed on the same line is text), closed on a later line with field boundaries between,
  gives `{field, kind: "macro-ambiguous", lines}` in `needs_decision`, and `get` and `set` refuse the fields it touches (the one it opens in and each it would hide);
- a heading-shaped line that ends no field (indented, or behind `>` or a list marker) is content;
  a renderer may still show it as a heading, so one naming the requested field makes `get` and `set` refuse (exit 2) instead of guessing;
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
| 2 | CLI argument error (e.g. both `--value` and `--value-file` given), or `get` / `set` refused an ambiguous field (`AmbiguousFieldError`): a heading naming the field sits behind `>`, a list marker or an indent. Every read and write runs this check itself; `set` also refuses a new value holding a line that would end the field, a replaced value (old or new) holding a heading-shaped line outside fences, and a rewrite that would change any other field or move its heading into or out of a closed block. The body is untouched. |
| 3 | Field heading not found, or matched more than once outside closed code blocks (`DuplicateFieldError`, a `FieldNotFoundError`). The body is untouched. |
| other | `gh` returned non-zero; the underlying `gh` stderr is forwarded. |
