<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the compiled-artifacts sub-check from Step 4 of the
pr-management-code-review skill from the Apache Magpie framework.

ASF releases must be source-only. When the diff adds any of the following
file types, raise a major finding:

- JVM: .class, .jar (non-empty), .war, .ear
- Python: .pyc, .pyo, .pyd
- Native: .so, .dll, .dylib, .exe, .o, .a
- Packages: .whl, .egg

Escalate to **blocking** only when the PR content gives **explicit**
evidence that the file is included in a release archive (for example a
statement that it ships in the sdist/wheel, or its presence in release
packaging configuration). Do **not** infer release inclusion from the
directory path or file name alone. A build-output directory such as
`dist/` is not by itself proof that the file is in the release archive.
When there is no explicit evidence of release inclusion, the severity is
**major**.

The `reason` must be a **definitive** statement that committing the
compiled artifact violates the ASF source-only release policy, and must
**recommend removing the file** (generating it at build time instead). Do
not phrase it tentatively or stop at a severity assessment.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "severity": "blocking" | "major",
      "reason": "<one sentence citing the rule>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
