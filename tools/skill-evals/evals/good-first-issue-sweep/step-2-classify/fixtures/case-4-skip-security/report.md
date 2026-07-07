<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #201

Title: API token not invalidated after password change

Body:
When a user changes their password, their existing API tokens remain
valid indefinitely. An attacker who obtains a token can continue using
it even after the account owner resets their credentials.

Steps to reproduce:
1. Log in and generate an API token.
2. Change the account password.
3. The old token still authenticates successfully.

Expected: tokens should be invalidated (or flagged for re-auth) on
password change.

Relevant code is likely somewhere in the auth or token-management layer,
but the exact files are not yet pinpointed.

Labels: bug, security
