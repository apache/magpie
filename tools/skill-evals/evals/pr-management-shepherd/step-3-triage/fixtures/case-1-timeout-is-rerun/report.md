<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR: #2105 "fix(maven-artifact-verify): refuse POMs that declare a DTD or entities"
mergeStateStatus: BLOCKED (one approval required)
autoMergeRequest: enabled
Files changed: tools/maven-artifact-verify/src/maven_artifact_verify/__init__.py, tools/maven-artifact-verify/tests/test_maven_artifact_verify.py

Checks:
  prek            fail  15m35s
  pytest (maven-artifact-verify)  pass
  rat             pass
  tests-ok        pass

prek job log (tail):
  11:13:00 Run actions/cache
  11:17:06 Run uv tool install prek
  11:17:08 Run prek run --from-ref <base> --to-ref HEAD
  ruff check (workspace)........Passed
  mypy (workspace)..............Passed
  typos.........................Passed
  11:26:23 ##[error]The operation was canceled.
Job timeout-minutes: 15

Inline review comments: none
