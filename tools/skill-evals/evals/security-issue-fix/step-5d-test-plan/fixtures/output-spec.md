<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step 5d test plan

Return a JSON object with these fields. Do not include the prose test-plan text itself.

```json
{
  "has_existing_tests": <bool — plan lists existing tests that must continue to pass>,
  "has_new_tests": <bool — plan specifies new tests to be added>,
  "new_tests_skipped_justified": <bool — if no new tests, a justification is given (e.g. pure rename)>,
  "has_unit_test_command": <bool — exact uv run pytest command is included>,
  "has_precommit_command": <bool — prek run --from-ref main --stage pre-commit is included>,
  "has_typecheck_command": <bool — mypy / type-check command is included>
}
```

Every boolean field above MUST always be present in the returned object; never
omit a field. In particular, `has_unit_test_command` and `has_precommit_command`
MUST always be present: the plan always lists the exact unit-test invocation and
the `prek run --from-ref main --stage pre-commit` command, so both are `true`
in every scenario (they run even for a pure rename).

Rules:
- `has_new_tests` is true when the plan says new tests will be added, false when it says none are needed or are omitted.
- `new_tests_skipped_justified` is true only when `has_new_tests` is false AND a reason is given (e.g. "pure rename", "no new behaviour introduced").
- `has_unit_test_command` requires the exact `uv run --project ... pytest` invocation with a specific test path.
- `has_precommit_command` requires `prek run --from-ref main --stage pre-commit`.
- `has_typecheck_command` requires a mypy invocation with `--with "apache-airflow-devel-common[mypy]"`.
