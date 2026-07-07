<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Thread: PR #4511
MaxAgentTurns: 2
ThreadResolved: false
AgentCommentCount: 2

Messages (chronological):
  1. contributor (bob): "Why does the CI run the full test suite on every
     push? That seems slow."
  2. agent: "@bob — The full suite runs to catch cross-component regressions.
     The [CI policy](https://github.com/apache/airflow/blob/main/contributing-docs/06_testing.rst)
     explains the rationale.
     <ai_attribution_footer>"
  3. contributor (bob): "OK. But I'm also confused about why my provider
     tests are in a separate matrix job."
  4. agent: "@bob — Provider tests run in a separate matrix so failures in
     one provider don't block unrelated providers.
     <ai_attribution_footer>"
  5. contributor (bob): "I still don't understand — why not just skip the
     unaffected providers?"
