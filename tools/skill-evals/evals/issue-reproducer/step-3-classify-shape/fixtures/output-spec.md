<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "shape": "<one of: A | B | C | D | E-vague | E-precise | F | G | H>",
  "rationale": "<one sentence explaining why this shape was chosen>"
}
```

Shape taxonomy reference:
- **A** — self-contained single-file script that runs as-is (no external fixtures, no framework boilerplate)
- **B** — near-complete but requires minor additions (missing imports, missing `if __name__ == "__main__"`, etc.)
- **C** — framework test method (e.g. `def test_foo(self)`) needing a test class/runner wrapper
- **D** — multi-file project or requires external fixtures
- **E-vague** — a fragment or claim that CANNOT be turned into a faithful test without inventing unstated setup. If constructing a runnable reproducer would require guessing environment variables, backend/secrets configuration, fixtures, or the surrounding call context that the reporter never gave, it is **E-vague** — even when a bare code line and a specific exception (e.g. a `KeyError`) are shown. A single invocation line is NOT a clear entry point when you still cannot set up what it depends on.
- **E-precise** — a fragment or claim whose stated content is sufficient ON ITS OWN to construct a faithful test, with no invented setup required (an algebraic/specifiable claim, e.g. "`x?.y?.z` returns null on Maps but throws on user classes"). E-precise is instantiation of an explicit, self-sufficient claim; if you would have to invent inputs, structure, or configuration, it is E-vague instead.
- **F** — stack trace / error log only, no code
- **G** — configuration or data file (YAML, JSON, SQL) that must be fed to a tool
- **H** — prose-only description; no code or config supplied

Do not include any text outside the JSON object.
