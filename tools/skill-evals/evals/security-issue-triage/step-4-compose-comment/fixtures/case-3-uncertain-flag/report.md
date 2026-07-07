<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### Tracker

Issue: [example-s/example-s#231](https://github.com/example-s/example-s/issues/231)
Title: "Provider package installed via pip can execute code in scheduler at import time"
Scope label: providers

### Step 3 classification result

```json
{
  "disposition": "UNCERTAIN",
  "rationale": "The attacker model (malicious Python package installed by the operator) does not match any row in the trust-boundary cheat-sheet. The operator is trusted, but a compromised package in the operator's dependency tree is a supply-chain scenario outside the standard attacker roles. Tentative lean: VALID (external supply-chain attack reaching the scheduler), but the team should weigh in before a proposal is posted."
}
```

### Security Model verbatim quote

Section: "Airflow Security Model — Deployment Managers"
URL: https://airflow.apache.org/docs/apache-airflow/stable/security/security_model.html#deployment-managers

Quote to include verbatim (2-3 sentences):
"Deployment Managers have full control of the Airflow environment including
installing packages, configuring the system, and managing credentials.
Actions by Deployment Managers or software they install are considered
trusted and are outside the scope of Airflow's security model."

### @-mention routing

PR-author match: @alice (most recent fix touching provider EntryPoint loading,
  apache/airflow#38500, merged 2025-09-10)
Triager (exclude): @carol
