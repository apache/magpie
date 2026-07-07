<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Check results (all 8 checks ran):

  Check 1 (project settings.json): ✓
  Check 2 (user-scope hooks):       ✓
  Check 3 (hook scripts):           ✓
  Check 4 (claude-iso):             ✓
  Check 5 (pinned versions):        ✓
  Check 6 (sandbox.enabled):        ✓
  Check 7 (denial commands):        ✓
  Check 8 (project root):           ✗  .claude/settings.local.json absent — /home/dave/tracker-repo
                                        missing from allowRead and allowWrite; live read of .git/HEAD
                                        FAILED; second worktree /home/dave/tracker-repo-feat also
                                        missing settings.local.json

sandbox-add-project-root.sh helper installed: yes (~/.claude/scripts/sandbox-add-project-root.sh)
Snapshot drift: none
