You are executing the compiled-artifacts sub-check from Step 4 of the
pr-management-code-review skill from the Apache Steward framework.

ASF releases must be source-only. When the diff adds any of the following
file types, raise a major finding:

- JVM: .class, .jar (non-empty), .war, .ear
- Python: .pyc, .pyo, .pyd
- Native: .so, .dll, .dylib, .exe, .o, .a
- Packages: .whl, .egg

If the file would be included in a release archive, escalate to blocking.
Otherwise the severity is major.

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
