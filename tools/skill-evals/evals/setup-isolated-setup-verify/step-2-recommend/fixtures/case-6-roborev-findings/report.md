<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check results:

  Check 1 (project settings.json): ✓
  Check 2 (user-scope hooks):       ✓
  Check 3 (hook scripts):           ✓
  Check 4 (claude-iso):             ✓
  Check 5 (tool versions):          ✓
  Check 6 (sandbox.enabled):        ✓
  Check 7 (denial commands):        ✓
  Check 8 (project root):           ✓
  Check 17 (roborev exclusion):     ✗  17b ✗ permissions.allow has Bash(roborev review *);
                                       17e ✗ no Bash(roborev *) ask rule in any scope;
                                       17f ⚠ post-commit hook runs roborev and .roborev.toml is untracked (?? .roborev.toml), operator has not confirmed writing it

Snapshot drift: none
