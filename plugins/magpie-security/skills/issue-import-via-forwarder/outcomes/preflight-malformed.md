<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — a malformed message

`preflight` printed `outcome: abort` and exited `2`. From Step 0:

3. **The in-hand message is structurally valid.** It must carry a `From:` header, a non-empty body, and a `Date:`.
   A relay message stripped of its headers is not a relay message — fail fast rather than guess.
