<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "module_run_clean": true | false,
  "regression_introduced": true | false,
  "verdict": "proceed | iterate"
}
```

`module_run_clean` is true when the module test suite exits with no failures.
`regression_introduced` is true when a test that is unrelated to the fix is now failing — i.e., the fix broke adjacent code.
`verdict` is `proceed` when the module run is clean; `iterate` when a regression is present.
Do not include any text outside the JSON object.
