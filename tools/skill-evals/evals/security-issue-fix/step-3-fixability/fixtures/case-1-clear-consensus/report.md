<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for airflow-s/airflow-s#272 (Pickle deserialization via XCom):

Labels: airflow, cve allocated
CVE: CVE-2025-44812
Milestone: 3.0.3

Discussion thread summary:
  jsmith: "The fix is straightforward — in `airflow/models/xcom.py` around
  line 180, the `deserialize_value` call needs to be gated behind a check
  that the caller is the XCom owner's original DAG, not a cross-DAG reader.
  Single-file change, no API change."

  mwilson: "Agreed. Approach 1 for me. The diff should be small — just add
  the owner-check before `pickle.loads` and add a test in
  `tests/models/test_xcom.py`."

  jsmith: "No open questions — reporter confirmed the PoC matches what we
  see. I'll draft the fix."

  mwilson: "+1 to proceed."

Fix PR: none yet
Security classification: valid, CVE-worthy (consensus)
Open questions: none
