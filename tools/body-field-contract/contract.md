<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Body-field contract](#body-field-contract)
  - [Lines](#lines)
  - [Field boundaries](#field-boundaries)
  - [Names](#names)
  - [Closed code blocks](#closed-code-blocks)
  - [Which heading is the field](#which-heading-is-the-field)
  - [Ambiguity: decisions, never guesses](#ambiguity-decisions-never-guesses)
  - [Operations](#operations)
    - [list fields](#list-fields)
    - [extract](#extract)
    - [replace](#replace)
    - [normalise](#normalise)
  - [What a writer must escape](#what-a-writer-must-escape)
    - [escape text](#escape-text)
    - [escape body](#escape-body)
  - [Format adapters](#format-adapters)
  - [Implementations](#implementations)
  - [Conformance suite](#conformance-suite)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Body-field contract

A tracker issue body is a sequence of named fields, each a `### <Name>` heading followed by its value.
Every reader and writer of those fields (the GitHub tool, vetted-ops, the local-files tracker, the Jira bridge, the CVE JSON generator, and any implementation in another language) MUST read and write them by the rules below, so that one body gives one set of fields to all of them.
The rules are written so a reporter's text, however it is formatted, can never become a field or make one field absorb another: in particular, the private mailing-list thread can never be read into the public summary.

The key words MUST, MUST NOT, SHOULD and MAY are to be read as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).
Each rule has an identifier (`BF-…`); every case of the [conformance suite](#conformance-suite) names the rule it tests.
The field roles and names a project uses are described in [`tools/github/issue-template.md`](../github/issue-template.md); this document is the authoritative statement of how fields are found.

## Lines

- **BF-LINE-1.** A line ends at `\n`, `\r\n` or `\r`, or at the end of the body. An implementation MUST keep each line's ending when it splits, so that joining the lines gives the body back byte for byte.
- **BF-LINE-2.** No other character ends a line: form feed, vertical tab, `U+0085`, `U+2028`, `U+2029` and the like are line content. (Python's `str.splitlines` breaks on them; an implementation MUST NOT use such a splitter.)

## Field boundaries

- **BF-BOUND-1.** A line is a *field boundary* if and only if it starts, at column 0, with `###` followed by a space, a tab or the end of the line. A bare `###` is a boundary with an empty name.
- **BF-BOUND-2.** Every field boundary ends the field before it and starts a new section, **whether or not it sits inside a code block**. A field's value is always exactly one section of that split; no fence, Jira macro or duplicate heading can extend it past the next boundary.
- **BF-BOUND-3.** `####`, `###x`, and a `###` line behind indentation, `>` or a list marker are not boundaries. Text before the first boundary is a preamble and belongs to no field.

## Names

- **BF-NAME-1.** A boundary's name is the rest of the line with leading and trailing spaces and tabs removed and then a closing run of `#` removed, when that run stands alone or follows a space or tab (`### Severity ##` names `Severity`; `### C#` names `C#`).
- **BF-NAME-2.** Names compare exactly: case-sensitive, inner whitespace significant. Only [normalise](#normalise) with known field names collapses inner whitespace (BF-NORM-3). An implementation MAY offer a lenient lookup (case-folded, whitespace-collapsed) as a documented extension, provided two lenient matches outside closed blocks are a duplicate (BF-SEL-2).

## Closed code blocks

A *closed block* is a code block whose opener and closer are both present. Blocks are found by one scan over the whole body, independent of field boundaries.

- **BF-BLOCK-1.** A CommonMark fence opener is a line of up to three spaces, then a run of three or more backticks or three or more tildes, then an info string. A backtick run whose info string holds a backtick is not an opener. Four or more spaces of indentation is not an opener.
- **BF-BLOCK-2.** A fence is closed by a later line of up to three spaces, then a run of the *same* character at least as long as the opener's, then nothing but spaces or tabs.
- **BF-BLOCK-3.** A Jira block opener is a line that starts, after spaces or tabs, with `{code}`, `{code:<anything>}` or `{noformat}`, and does not hold a second occurrence of that macro's name. It is closed by the next line holding the bare macro (`{code}` or `{noformat}`) anywhere.
- **BF-BLOCK-4.** Inside an open block, nothing else opens: a fence inside a `{code}` block, or a `{code}` inside a fence, is content.
- **BF-BLOCK-5.** A block left open at the end of the body is not a closed block: it marks nothing.

## Which heading is the field

- **BF-SEL-1.** The field named *N* is the one section named *N* whose boundary lies **outside every closed block**. A boundary inside a closed block never starts a field: a field whose only copies are inside closed blocks is absent (not found), never read from the quoted copy.
- **BF-SEL-2.** Two or more sections named *N* outside closed blocks are a *duplicate*: reading or writing *N* MUST fail, whatever the copies hold.
- **BF-SEL-3.** A field's value is its section's lines after the boundary, with at most one leading blank line and at most one trailing blank line (when the section has more than one line) removed. Other blank lines are kept.
- **BF-SEL-4.** The list of a body's fields is the names of the sections outside closed blocks, in document order, repeats included.

## Ambiguity: decisions, never guesses

Some bodies read differently in different renderers. An implementation MUST NOT pick a reading; it reports a *decision* and refuses the field.

- **BF-CONT-1. Container headings.** A heading-shaped line that is not a boundary (`###` behind indentation, `>` or list markers, any number of them) is content. When it names the requested field and sits outside a fence, as a CommonMark reader pairs fences or as a reader that only accepts fences at column 0 does, reading or writing that field MUST fail as ambiguous. [Normalise](#normalise) reports it as a `container-heading` decision for known field names.
- **BF-MACRO-1. Jira macros opened mid-line.** Jira's renderer opens `{code}` and `{noformat}` anywhere in a line. A line outside closed blocks that, pairing its macros left to right, leaves one open, followed by a later line closing it, with one or more field boundaries between, is a `macro-ambiguous` decision. Reading or writing the field the macro opens in, or any field whose boundary it would hide, MUST fail as ambiguous. A macro opened and closed on the same line is text; one never closed hides nothing.

## Operations

Every implementation provides these four operations; a writer of untrusted text also provides the [writer operations](#what-a-writer-must-escape). Errors are one of three kinds: `not_found`, `duplicate` (a not-found kind for callers that only distinguish found from not found) and `ambiguous`.

### list fields

- Input: a body. Output: the field names (BF-SEL-4). Never fails.

### extract

- Input: a body and a field name. Output: the field's value (BF-SEL-3), with its own line endings.
- **BF-EXT-1.** Fails `ambiguous` under BF-CONT-1 or BF-MACRO-1, checked before anything else; `not_found` when the field is absent (BF-SEL-1); `duplicate` under BF-SEL-2.

### replace

- Input: a body, a field name and a new value. Output: the new body.
- **BF-REP-1.** Everything outside the field's value is preserved byte for byte, the heading line included. The value is written in the line-ending convention of the field's heading line; a run of trailing line endings is reduced to one, and a value with content always ends in one. The blank-line spacer after the heading and before the next field is kept when the old value had it. An empty value leaves one spacer line, or none for the last field. Replacing a value with itself returns the body unchanged.
- **BF-REP-2.** Fails as [extract](#extract) does for the field.
- **BF-REP-3.** Fails `ambiguous` when the new value holds a field boundary (BF-BOUND-1) on any line, split by BF-LINE-1 — inside a fence or not.
- **BF-REP-4.** Fails `ambiguous` when the old or the new value holds a heading-shaped line outside fences (behind any indentation, `>` or list marker).
- **BF-REP-5. Whole-body preservation.** Fails `ambiguous` unless the rewritten body has the same sections, each boundary inside or outside closed blocks as before, every other section byte-identical, and no `container-heading` or `macro-ambiguous` decision. A value that opens a fence or a macro reaching past its field is refused this way.

### normalise

- Input: a body, optionally known field names and a *keep* map (field name → the input line number of the copy to keep). Output: the canonical text, a list of *changes* `{line, kind}` and a list of *decisions* `{field, kind, lines}`. Line numbers are 1-based lines of the input; changes are ordered by line, then kind. Never fails.
- **BF-NORM-1.** `\r\n` and lone `\r` become `\n`; one `line_endings` change at the first such line.
- **BF-NORM-2.** A fence left open is closed in the field it opens in, after the last non-blank line before the next boundary (`unclosed_fence`, at the opener), unless the closer would move a boundary into or out of a closed block; then it stays open.
- **BF-NORM-3.** A boundary outside closed blocks is rewritten `### <Name>` (`heading`); with known field names, a name equal to one once inner whitespace is collapsed (case kept) takes the known spelling (`heading_name`). Lines inside closed blocks are never rewritten.
- **BF-NORM-4.** Copies of a field outside closed blocks that hold the same value (after stripping) collapse to the first (`duplicate_dropped`, at each dropped heading). Differing copies stay and give a `duplicate` decision listing their heading lines, unless *keep* names one of them, which is kept (`duplicate_resolved`). Copies inside closed blocks are never counted, dropped or reported.
- **BF-NORM-5.** `container-heading` decisions (BF-CONT-1, for known names) and `macro-ambiguous` decisions (BF-MACRO-1: the first hidden field; the opener's line, then each hidden boundary's) are reported, never resolved.
- **BF-NORM-6.** Normalising a normalised body changes nothing.

## What a writer must escape

A writer that puts untrusted text (a report, a comment, a scanner finding) into a body provides one or both of two writer operations, and MUST follow the rules below.
Escaping is a leading `\` on the line, which renders as the same visible text and is never parsed as structure; nothing else on the line changes.

### escape text

- Input: untrusted text that will become (part of) one field's value. Output: the escaped text. Never fails (a writer MAY refuse text instead of escaping it).
- **BF-WRITE-1.** Every line of the text that is a field boundary (BF-BOUND-1), split by BF-LINE-1, MUST be escaped. Heading-shaped lines behind indentation, `>` or list markers SHOULD be escaped too, for readers that ignore fences (cases tagged `escape-loose`).
- **BF-WRITE-3.** The rule holds inside fences and Jira macros: a writer MUST NOT rely on a block to protect text, since blocks only decide which heading is the field (BF-SEL-1), never where a field ends.

### escape body

- Input: a whole body whose own boundaries are its fields (a report a writer stores as is). Output: the escaped body. Never fails.
- **BF-WRITE-2.** Every field boundary inside a closed block (BF-BLOCK-1 to BF-BLOCK-5) MUST be escaped, so quoted text never becomes a copy of a field; boundaries outside closed blocks, and every other line, MUST be left as they are.
  A writer SHOULD also close a fence the body leaves open in the field it opens in (as BF-NORM-2 does), never past another field's boundary.

## Format adapters

A project whose reports keep their fields in another layout (`Name: value` lines, a plain-text CVE file) reads and writes them through a *format adapter*:
the operations above for that layout's own boundary rule, in place of BF-BOUND-1 to BF-BOUND-3 and BF-BLOCK-*.
The local-files tracker loads one only when its descriptor says `field_layout: custom` and names the adapter, and a human has confirmed the adapter's hash
([`tools/local-tracker`](../local-tracker/README.md#custom-field-layouts)).
[`formats/`](formats/README.md) is the upstream home for adapters other projects can reuse; [`formats/_template.py`](formats/_template.py) is the skeleton.

- **BF-FMT-1. Interface.** An adapter is one Python module using the standard library only, providing:
  `FORMAT` and `DESCRIPTION` (the layout's name and one line describing it);
  `boundary_name(line)` (the field a line starts, or None: the layout's one boundary rule) and `boundary_line(name)` (the line that starts field *name*);
  `list_fields(body)`, `extract_field(body, name)`, `replace_field(body, name, value)` and `normalise(body, known_fields=None, keep=None)` with the inputs, outputs and errors of [Operations](#operations);
  `append_field(body, name, value)`, which adds a field after the last one and fails `duplicate` when it exists;
  the errors `FieldNotFoundError`, with `DuplicateFieldError` and `AmbiguousFieldError` as subclasses;
  and `SAMPLE_BODY` / `SAMPLE_FIELDS`, a body in the layout with its fields, built from **synthetic** values only.
- **BF-FMT-2. Rules every layout keeps.** BF-LINE-1 and BF-LINE-2 (lines and their endings), BF-SEL-2 (a duplicate fails), BF-EXT-1 (absent and duplicate fields fail, never guessed),
  BF-REP-1 (everything outside the field byte for byte, in the body's line-ending convention), BF-REP-3 (a value holding a line that would start a field is refused),
  BF-REP-5 (whole-body preservation), BF-NORM-1, BF-NORM-4 and BF-NORM-6.
- **BF-FMT-3. Fixtures.** An adapter ships `<name>.cases.jsonl` beside it, in the [conformance case format](#conformance-suite), with synthetic values only, never text copied from a report;
  the conformance suite runs it, and the generic properties of BF-FMT-2 over `SAMPLE_BODY`, before the adapter is enabled.

## Implementations

| Implementation | Language | Status | Notes |
|---|---|---|---|
| [`tools/github-body-field`](../github-body-field/README.md) (`github_body_field.parser`) | Python | reference | The source every Python copy is pinned to. |
| [`tools/vetted-ops`](../vetted-ops/README.md) (`vetted_ops.body_field_format`) | Python | byte-identical copy | Pinned by `tests/test_body_field_parity.py`. |
| [`tools/local-tracker`](../local-tracker/README.md) (`magpie_local_tracker.body_field_format`, used by `sections`) | Python | byte-identical copy | Pinned by `tests/test_vendored_parser.py`; lenient name lookup (BF-NAME-2). Writer: escape text (`sections.escape_field_lines`), escape body (`sections.escape_quoted_fields`). |
| [`tools/jira`](../jira/README.md) (`jira_bridge.body_field_format`, used by `markup`) | Python | byte-identical copy | Pinned by `tests/test_vendored_parser.py`; reads wiki `h1.`–`h3.` headings outside closed blocks as `### <Heading>` first, lenient name lookup. Writer: escape body (`markup.escape_quoted_fields`). |
| [`groovy/`](groovy/BodyFieldParser.groovy) (`BodyFieldParser`) | Groovy | basic implementation | Every operation, the writer operations included; exact name lookup. Dependency-free (the Groovy runtime only). Runs the suite through `groovy/conformance.groovy`. |
| [`tools/security-management`](../security-management/README.md) (`security_management.shared.body.inert_block`) | Python | writer only | Escape text: the import's inert block, which escapes the lines inside its own fence. |

## Conformance suite

[`conformance/cases.jsonl`](conformance/cases.jsonl) holds the language-neutral cases, one JSON object per line:

```json
{"id": "outside-copy-wins", "clause": "BF-SEL-1", "op": "extract",
 "body": "### A\n\n```\n### Severity\nCritical\n```\n\n### Severity\n\nLow\n",
 "args": {"name": "Severity"}, "tags": [], "expect": {"value": "Low\n"}}
```

- `op` is `list_fields`, `extract`, `replace`, `normalise`, `escape_text` or `escape_body`; `args` holds `name` (extract, replace), `value` (replace), `known_fields` and `keep` (normalise, optional). The input body or text is `body`.
- `expect` is `{"value": …}` (a list of names, a value, a body, or `{"text", "changes", "needs_decision"}`) or `{"error": "not_found" | "duplicate" | "ambiguous"}`.
- `tags` mark cases that depend on an optional behaviour: `case-sensitive` and `inner-whitespace` (exact name matching, BF-NAME-2), which an implementation documenting a lenient lookup skips, and `escape-loose` (the SHOULD of BF-WRITE-1), which a writer that escapes only boundaries skips.
- An implementation runs the `escape_text` and `escape_body` cases only for the writer operations it provides; a reader provides neither.

`tools/github-body-field/tests/test_conformance.py` runs every case against every implementation in the repository through a thin adapter per implementation, and fails on the first case an implementation gets wrong.
A format adapter runs through the same suite: its own fixtures and the generic properties (BF-FMT-3), for every adapter in [`formats/`](formats/README.md) and any named by `BODY_FIELD_FORMAT_ADAPTERS` (paths separated by the platform's path separator).
A new implementation (in another language, say) conforms by providing an adapter that, for each case, calls its own operation and returns the result in the `expect` shape — values compared exactly, errors by kind — and passes every case whose tags it does not opt out of.
The simplest adapter is a program that reads `cases.jsonl` and prints one JSON object per line, `{"id", "result"}`, which the pytest runner compares; add it to the runner's adapter table with the condition under which it can run (a skip with a reason when its runtime is absent).
The Groovy implementation is run this way:

```bash
groovy -cp tools/body-field-contract/groovy tools/body-field-contract/groovy/conformance.groovy \
    tools/body-field-contract/conformance/cases.jsonl
```

`test_groovy_conformance` runs that command when `groovy` is on `PATH` and compares every line with the case's `expect`; without `groovy` it skips, saying so.
No CI workflow installs Groovy, so in CI that check is skipped; it runs wherever a contributor has Groovy installed.
