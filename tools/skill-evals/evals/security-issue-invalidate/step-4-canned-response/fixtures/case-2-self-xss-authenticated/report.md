<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Reasoning summary extracted from tracker discussion

**Tracker #305 — "Stored XSS via DAG description field in web UI"**

Team reasoning quotes:

- @triager-b: "The DAG description is rendered in the UI only for users who already have authenticated access to the Airflow web UI. An attacker exploiting this would need to already have DAG write access, which implies full trusted DAG author privileges."
- @triager-c: "This is self-XSS by an authenticated user. The reporter controls the DAG description field directly. There is no cross-user XSS path here — other users viewing the description would need to be in the same authenticated session context."
- @triager-b: "Authenticated user XSS where the attacker and victim are the same user does not meet our CVE bar."

**Invalidity classification:** Self-XSS triggered by an authenticated user who controls the input field.
