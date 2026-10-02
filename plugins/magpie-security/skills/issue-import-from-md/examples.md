<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — examples

## Examples

### Example 1 — A six-finding AI-scan output

In this example the filename happens to follow a
`<reporter>-<project>-<date>` convention — your project's
file-naming convention is irrelevant to the skill; the basename
just gets carried into the rollup comment verbatim.

```text
import findings from /tmp/scan-reporter-product-2026-04-28.md
```

The skill parses six findings (severities: HIGH×2, MEDIUM×2,
LOW×2). The duplicate guard flags one HIGH as a possible
duplicate of an already-tracked deserialization finding; the user
replies `skip 1`, accepting the duplicate hint. The remaining five
land as `<tracker>#NNN..#NNN+4` in `Needs triage`. Recap shows
the five new tracker URLs and one skip with the duplicate
reference.

### Example 2 — A single-finding scanner export

```text
import findings from ~/Downloads/sast-export.md
```

The file contains one finding (a SAST report exported as
markdown). The skill parses, surfaces a one-row proposal, the
user replies `go`, the tracker lands. The cardinality is the same
as a Gmail import; the only difference is the source format.

### Example 3 — Malformed input

```text
import findings from /tmp/notes.md
```

`/tmp/notes.md` is a free-form scratch file — no `**Severity:**`
lines, no `---`-separated blocks. Step 0's sanity check fires;
the skill stops with the expected-shape ask and does not create
any tracker.
