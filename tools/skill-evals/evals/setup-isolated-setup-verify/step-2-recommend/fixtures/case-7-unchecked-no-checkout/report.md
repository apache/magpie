<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check results:

  Check 1 (effective settings):     ✓
  Check 2 (user-scope hooks):       ✓
  Check 3 (hook scripts):           ✓
  Check 4 (claude-iso):             ✓
  Check 5 (tool versions):          ⚠ no framework checkout: pins unchecked, claude-code min_version floor not enforced (installed: bubblewrap 0.11.2, socat 1.8.1.3, claude-code 2.1.210)
  Check 6 (sandbox.enabled):        ✓
  Check 7 (denial commands):        ✓
  Check 8 (project root):           ✓
  Check 10 (touch overlay):         unchecked — no framework checkout (10a script comparison; every other sub-check ✓)

Framework checkout: none found — no .apache-magpie/ snapshot, the shell rc sources a user-scope copy, and the user has no magpie clone.
Snapshot drift: none
