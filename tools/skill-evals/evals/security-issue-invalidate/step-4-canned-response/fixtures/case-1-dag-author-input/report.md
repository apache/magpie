<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Reasoning summary extracted from tracker discussion

**Tracker #318 — "BashOperator executes arbitrary commands from DAG definition"**

Team reasoning quotes:

- @triager-a: "The DAG author is a trusted principal in Airflow's security model. BashOperator is explicitly designed to execute commands supplied by the DAG author. Treating the DAG author's own code as an untrusted attack vector inverts the trust model."
- @triager-b: "This is working as intended. The security model page documents that DAG authors are trusted to run arbitrary code on worker nodes."
- @triager-a: "The reporter is claiming that a DAG author can execute shell commands via BashOperator — that is the feature, not the vulnerability."

**Invalidity classification:** The attack vector is DAG-author-provided input; DAG authors are trusted principals.
