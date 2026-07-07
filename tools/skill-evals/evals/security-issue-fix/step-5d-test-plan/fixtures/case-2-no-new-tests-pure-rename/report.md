<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Fix plan context

**File changed:** `airflow/utils/security.py`
**Change:** Rename internal helper `_check_pwd` to `_validate_password_strength` — pure rename, no logic change. The function is private and not part of any public API.

**Existing test file:** `tests/utils/test_security.py`
- `TestSecurity::test_validate_password_strength` — already references the function by import; the rename will require updating the import in the test, but no new test logic.

**New tests required:** No — this is a pure rename with no new behaviour introduced. The existing test suite fully exercises the renamed function.

**Type-check applicable:** No — the function has no type annotations and the module is excluded from mypy in `pyproject.toml`.

Produce the test plan for step 4d.
