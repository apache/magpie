<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "test_has_issue_key": true | false,
  "adapts_from_reproducer": true | false,
  "confirmed_failing": true | false,
  "verdict": "accept" | "reject" | "surface-gap"
}
```

`verdict` must be exactly one of the string tokens `"accept"`, `"reject"`,
or `"surface-gap"` (no other value, no combined string).

`test_has_issue_key` is true when the issue key appears in the test name or a docstring/comment.
`adapts_from_reproducer` is true when a reproducer verdict was supplied and the test is based on it; false when no reproducer was provided (acceptable) or when a reproducer was provided but the test ignores it (not acceptable).
`confirmed_failing` is true ONLY when the test run output shows the test fails on the default branch as expected. When the run output shows the test PASSED on main, `confirmed_failing` is false.
`verdict` is `"accept"` when all properties hold; `"surface-gap"` when the run output shows the test PASSED on main; `"reject"` only when a required structural property is missing (no issue key in the test, wrong test framework, or a supplied reproducer is ignored). Decide in this order: FIRST, if the run output shows the test PASSED on main, the verdict is `"surface-gap"` — full stop, regardless of anything else, and even if the test looks like it asserts the buggy/wrong value (that is exactly the silent-broken-test trap, not a reason to reject). Only if the test actually failed on main do you consider `"accept"` vs `"reject"`. A test that passes on main is NEVER `"accept"` and NEVER `"reject"`; it is always `"surface-gap"`. "Malformed" for reject purposes means a missing structural property, not "the test asserts the wrong behaviour."
Return ONLY a single JSON object, no fences, no commentary. Do not include any text outside the JSON object.
