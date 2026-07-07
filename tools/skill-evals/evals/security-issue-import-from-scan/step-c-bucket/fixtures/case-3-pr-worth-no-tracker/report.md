<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

#### FINDING-003: Error handler returns the raw exception text regardless of expose_stacktrace

| Attribute | Value |
|-----------|-------|
| Severity | Medium |
| Attacker Capability Required | An authenticated API consumer able to trigger the error. |
| Impact | Limited information disclosure (exception message; no stack trace). |

Description: the handler interpolates the raw exception text into the HTTP 500 detail, ignoring the expose_stacktrace setting that its sibling handler honours. Limited sensitivity.

Remediation: gate the raw text behind expose_stacktrace and log server-side, mirroring the sibling handler.
