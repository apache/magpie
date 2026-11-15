<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR: #2102 "feat(isolated-setup-verify): run the mechanical checks as code"
mergeStateStatus: BLOCKED (one approval required)
autoMergeRequest: enabled
Files changed: plugins/magpie-setup/skills/setup/setup_preflight/isolated_verify.py, tools/setup-preflight/tests/test_isolated_verify.py

Checks: all pass

Inline review comments on the current head:
  github-advanced-security[bot] on isolated_verify.py:134
    "CodeQL / Unnecessary lambda: This 'lambda' is just a simple wrapper around a callable object. Use that object directly."
  github-advanced-security[bot] on isolated_verify.py:297
    "CodeQL / Empty except: 'except' clause does nothing but pass and there is no explanatory comment."
