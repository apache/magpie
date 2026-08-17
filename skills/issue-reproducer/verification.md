<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Verification — comparing the run to the reporter's claim

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 7:
deciding what the run actually means.

## The classification labels

The full set of classifications, with criteria:

| Label | When |
|---|---|
| `fixed-on-master` | Reproducer ran cleanly; the failure the reporter described is not present on `<default-branch>` |
| `still-fails-same` | Reproducer failed with the same exception class AND a message containing the reporter's substring (or analogous match for non-throw failures) |
| `still-fails-different` | Reproducer failed, but with something materially different from the reporter's claim |
| `cannot-run-extraction` | Shape didn't support adaptation (see [`extraction.md`](extraction.md)) |
| `cannot-run-environment` | Run errored before exercising the reporter's path (missing tool, broken JDK / interpreter) |
| `cannot-run-dependency` | Dependency resolution failed (see [`runtime-recipes.md` → *"Network and dependency handling"*](runtime-recipes.md#network-and-dependency-handling)) |
| `timeout` | Exceeded the bounded run |
| `intended-behaviour` | Reporter's expectation was wrong; observed behaviour is correct per project docs |
| `duplicate-of-resolved` | A closed sibling issue already covers this report |
| `needs-separate-workspace` | Multi-file project requiring its own build (shape H) |

The label is one of these — never *invent* a new label, even when
the situation is liminal. When the run sits between two labels,
pick the one the evidence supports best and explain in
`verdict.json.notes`.

## Comparing to the original failure

`still-fails-same` requires **both**:

1. **Same exception class** (or analogous failure mode for non-
   throw failures — same return value, same wrong output).
2. **Message-substring match** against the reporter's claimed
   error message. Use anchored regex, not bare `contains()`.

If only (1) matches and the message is materially different,
classify `still-fails-different` and note the actual message in
`verdict.json.notes`.

If only (2) matches and the exception class differs, classify
`still-fails-different` — same human-readable text can come from
different code paths.

If neither matches, the reproducer no longer fails at all
(`fixed-on-master`) or fails in an unrelated way
(`still-fails-different`).

## Substring-match pitfalls

The most common silent-false-positive in verification logic:
substring matching near common prefixes.

**Bad:**

```python
if "xs" in output:                       # matches xsi too
    classified = "still-fails-same"
```

**Bad:**

```groovy
if (output.contains("foo")) {            // matches foo-bar, foobar
    classified = "still-fails-same"
}
```

**Good — anchored regex:**

```python
import re
if re.search(r'\bxs="[^"]*"', output):   # match only xs= attribute
    classified = "still-fails-same"
```

**Good — parsed-tree inspection** (when the output is structured):

```groovy
def doc = new XmlSlurper().parseText(output)
def hasXsNamespace = doc.@*.find { it.name() == 'xs' } != null
```

The "verify identifiers" discipline applies to the verification
logic itself, not just the code under test. Almost-shipped false
`fixed-on-master` verdicts have hit this trap.

## Locale, line-endings, and format dependencies

Outputs captured on different platforms or locales can diverge
without the underlying behaviour changing:

- **Line endings** — captured on Windows uses `\r\n`; Unix uses
  `\n`. Normalise to `\n` before comparing strings.
- **Locale-dependent formatting** — number separators (`1,000.0`
  vs `1.000,0`), date formats, currency. If the reporter's claim
  references a formatted value, the comparison must normalise to
  a canonical form first.
- **Charset** — non-ASCII content captured under a non-UTF-8
  default. Always pass `--encoding utf-8` or equivalent on the
  capture command and normalise the file on read.
- **Default JDK / interpreter version** — Step 7 records the
  version; the classification doesn't depend on it directly, but a
  `passes` verdict captured under JDK 21 doesn't necessarily mean
  the bug is fixed on the JDK 8 the reporter ran.

When the comparison normalises, document the normalisation in
`verdict.json.notes` so the verdict is reproducible.

## Multi-case verification

When the reproducer is multi-case (per
[`extraction.md` → *"Picking the candidate"*](extraction.md#picking-the-candidate)),
verify each case independently:

1. Run each case in its own pass through Step 6 (separate
   `<runtime>` invocation, separate captured streams).
2. For each case, produce the `(case-id, expected, actual,
   match_on_master)` tuple.
3. Aggregate into `verdict.json.cases` per
   [`verdict-composition.md`](verdict-composition.md).
4. The overall `classification` for the issue is:
   - `still-fails-same` if any case still fails as the reporter
     described AND no case has a different failure mode than
     before.
   - `still-fails-same` *partial-fix* if some cases now pass that
     used to fail (record details in `cases_summary`); the
     `nature` field is `bug-as-advertised-partial-fix`.
   - `fixed-on-master` only if **every** case now passes that
     used to fail.

The `cases_summary` line is a one-line roll-up the campaign
dashboard surfaces (e.g., *"8/10 boundary cases pass on master;
2 still throw"*).

## Historical baselines

If maintainers have commented prior runs (*"I tried this in
version X and got Y"*), the verdict's headline framing can use
the baseline as the comparison point:

- *"State unchanged since maintainer's 2018 baseline (still
  throws)"* — more informative than *"still-fails-same"*.
- *"State improved since maintainer's 2018 baseline (passes
  now)"* — calibrates *"when did it start working"*.

Record each baseline in `verdict.json.cases[].history` (year,
status, source URL or comment-link) per
[`verdict-composition.md`](verdict-composition.md).

## Sanity-checks before locking the verdict

Before writing `verdict.json` and proceeding to the next issue:

- **Did the run actually exercise the reporter's path?** A
  `passes` verdict that ran a different code path (because the
  adaptation differed) is misleading. Re-read
  `<scratch>/reproducer.<ext>` against the reporter's original;
  diff if useful.
- **Is the substring match anchored?** Re-grep the captured output
  for the reporter's substring with anchored boundaries to
  confirm the match isn't a near-prefix coincidence.
- **Are both streams captured?** Some failure indicators land in
  stderr only.
- **Is the environment recorded?** Rev, runtime version, command
  — all in `verdict.json` per
  [`verdict-composition.md`](verdict-composition.md).

A draft verdict that fails any sanity-check is rewritten before
locking, not posted.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration.
- [`extraction.md`](extraction.md) — how the shape was determined
  (drives the `cannot-run-*` labels).
- [`runtime-recipes.md`](runtime-recipes.md) — how the run
  produced the output being verified.
- [`verdict-composition.md`](verdict-composition.md) — the schema
  the verdict slots into.
- [`probe-templates.md`](probe-templates.md) — cross-family probe
  pattern that can disambiguate liminal cases.
