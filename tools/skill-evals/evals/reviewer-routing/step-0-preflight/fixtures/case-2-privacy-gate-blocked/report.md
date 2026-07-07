<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /reviewer-routing issue:17

gh auth status: authenticated as maintainer-ops (read scope confirmed).

project.md:
  upstream_repo: apache/example
  upstream_default_branch: main

projects/apache-example/reviewer-roster.md found (non-ASF profile):
  2 roster entries loaded.

Input resolved: issue:17 → Issue 17 on apache/example.

privacy-llm-check: exit 1.
  ERROR: LLM endpoint 'https://api.thirdparty-vendor.io/v1' is not in
  the approved endpoint list for this project.
  Run 'privacy-llm-check --list' to see approved endpoints.
  Update privacy-llm.md to resolve.
