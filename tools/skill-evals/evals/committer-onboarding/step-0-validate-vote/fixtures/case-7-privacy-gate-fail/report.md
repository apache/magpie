<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project: Apache Airflow (incubating)
Candidate: Maria Santos
Candidate email: maria@example.com
Desired Apache ID: msantos
Existing Apache ID: none
Scenario: new-committer

privacy_gate_check_result:
  command: privacy-llm-check --reads-private-list
  exit_code: 1
  output: |
    ERROR: active LLM "claude-sonnet-4-6" is not listed as an approved model in
    <project-config>/privacy-llm.md under "Currently configured LLM stack".
    This skill reads private-list content. You must add the LLM to the approved
    stack before proceeding. See tools/privacy-llm/models.md for instructions.
