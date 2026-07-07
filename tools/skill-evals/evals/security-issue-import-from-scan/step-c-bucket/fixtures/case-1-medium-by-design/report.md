<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

#### FINDING-002: Provider builds a shell script by interpolating connection credentials without escaping

| Attribute | Value |
|-----------|-------|
| Severity | Medium |
| CWE | CWE-78 |
| Attacker Capability Required | A user who can create or edit the Connection's credential fields. |
| Impact | OS command execution on the host the provider connects to. |

Description: the provider interpolates Connection credential fields directly into a generated shell/script without neutralisation, so a crafted credential value injects commands. The credential bytes are controlled by whoever configures the Connection.

Remediation: neutralise credential fields before embedding them in script syntax.
