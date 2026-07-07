<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Fix plan context

**File changed:** `airflow/www/security.py`
**Change:** Add `netloc` validation to the `get_safe_redirect` function using `urllib.parse.urlsplit` to prevent open redirect.

**Existing test file:** `tests/www/test_security.py`
- `TestSecurity::test_get_safe_redirect_external` — tests that external URLs are blocked.
- `TestSecurity::test_get_safe_redirect_internal` — tests that internal paths are allowed.

**New tests required:** Yes — add `TestSecurity::test_get_safe_redirect_netloc_bypass` to assert that a URL with a `netloc` component (e.g. `//evil.com/path`) is rejected even when it lacks a scheme.

**Type-check applicable:** No — `airflow/www/` is excluded from mypy scope in the project configuration.

Produce the test plan for step 4d.
