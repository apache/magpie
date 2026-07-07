<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: Read /tmp/scanner-export-2025-04-15.md

```markdown
# Open redirect in login callback URL validation

## Details

The `_redirect_or_index` function in `airflow/www/security.py` validates
redirect URLs after login by checking only that the path does not start
with `//`. A URL starting with `\//` passes the check on Chromium-based
browsers because the browser normalises the backslash to a forward slash,
resulting in a redirect to an attacker-controlled domain.

## Location

[airflow/www/security.py#L88](https://github.com/apache/airflow/blob/main/airflow/www/security.py#L88)

## Impact

An attacker can craft a login link that redirects the victim to a phishing
page after successful authentication.

## Reproduction steps

1. Visit `https://airflow.example.com/login?next=\//evil.example.com/phish`
2. Log in with valid credentials.
3. Observe redirect to `evil.example.com`.

## Recommended fix

Normalise the URL with `urllib.parse.urlsplit` before the path check and
reject any URL with a non-empty `netloc` component.

---
**Severity:** CRITICAL
**Status:** Open
**Category:** Open Redirect
**Repository:** apache/airflow
**Branch:** main
**Date created:** 2025-04-15
```
