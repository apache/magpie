<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the security-model calibration sub-check from Step 4 of
the pr-management-code-review skill from the Apache Magpie framework.

Before flagging anything security-flavoured in a diff, calibrate it against
the project's **documented security model**. For this project the
documented model states:

- **Trusted DAG authors.** Code authored in a DAG (including operator
  arguments that execute Python or shell) runs with the privileges of the
  worker by design. DAG authors are a trusted role; their ability to run
  arbitrary code is a **documented, intentional limitation**, not a
  vulnerability.
- **Authenticated role-based access.** Actions available to an
  authenticated user with the appropriate role are by design.
- **Secrets are never logged.** Connection passwords and other secrets are
  stored encrypted at rest; writing a secret in plaintext to logs or to an
  unauthenticated response is a **vulnerability**.
- **Transport security is a deployment concern.** Whether TLS is terminated
  in front of the webserver, and what address it binds to, are the
  operator's responsibility; the documented model treats these as
  **deployment-hardening** matters, not code defects.

Classify the security-flavoured change in the diff into exactly one of:

- `vulnerability` — violates the documented model. Severity: `blocking`.
- `known-limitation` — matches an intentional, documented limitation.
  Severity: `none` (do not flag; quote the model when downgrading).
- `deployment-hardening` — an operator/deployment concern, not a code
  defect. Severity: `none` (route to deployment guidance, not a finding).

The `reason` must state the classification and cite the relevant part of
the documented model.

## Output

Return ONLY valid JSON with this structure:
{
  "assessment": {
    "classification": "vulnerability" | "known-limitation" | "deployment-hardening",
    "severity": "blocking" | "none",
    "reason": "<one sentence>"
  }
}

Do not include any text outside the JSON object.
