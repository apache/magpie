<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "blocks": [
    {
      "location": "body | comment-<N> | attachment-<filename>",
      "language": "python | java | bash | sql | yaml | other | unknown",
      "line_count": <integer>
    }
  ],
  "reporter_env": {
    "runtime_version": "<version string or null>",
    "os": "<OS string or null>",
    "notes": "<any other environment details or null>"
  },
  "block_count": <integer matching len(blocks)>
}
```

`runtime_version` captures the reporter's full runtime stack: the
framework/library version together with the language/interpreter version
(e.g. `"Airflow 2.9.1, Python 3.11"`). Put the operating system in `os`, not
in `runtime_version`, and keep any remaining environment details in `notes`.

Do not include any text outside the JSON object.
