<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Blocked — RC tag exists

**Likely cause:** `<version>-<rcN>` already exists on the remote.

**Remediation:** the RM decides whether to delete the tag (rare) or bump the RC number, then reruns with the new RC number.
Never advance past Step 0 while it exists.
