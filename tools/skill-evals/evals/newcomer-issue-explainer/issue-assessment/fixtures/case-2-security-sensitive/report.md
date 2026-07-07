<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #398

State: open
Labels: good first issue
Title: Fix authentication bypass in session token validation
Body:
When a user logs in with a malformed token, the session validation code
in `src/acme/auth/session.py` raises an uncaught exception that leaves
the session in an authenticated state. This is a security vulnerability
(CVE-2024-12345) that allows unauthenticated access to protected routes.

Fix the exception handling so that a malformed token results in an
authentication failure, not an authenticated session.

Relevant file: `src/acme/auth/session.py` — `validate_token` function.
Acceptance criteria: malformed tokens always result in a 401 response.
