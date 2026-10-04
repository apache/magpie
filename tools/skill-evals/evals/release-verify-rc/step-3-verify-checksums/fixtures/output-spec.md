<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 3 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "checksums",
  "status": "PASS" | "WARN" | "FAIL",
  "results": [
    {
      "file": "<artefact filename>",
      "digests": [
        {
          "type": "sha512" | "sha256" | "md5",
          "classification": "PASS" | "MISMATCH" | "MISSING-DIGEST"
        }
      ]
    }
  ],
  "deprecated_md5_present": true | false,
  "paste_recipe": "<multi-line shell commands>"
}
```

Grading rules:
- `status` must be `"FAIL"` if any non-md5 `classification` is `"MISMATCH"`
  or the required sha512 is `MISSING-DIGEST`.
- `status` must be `"WARN"` if the only anomaly is a deprecated `md5` file
  being present, matching or mismatched (md5 never fails alone).
- `status` must be `"PASS"` if sha512 and every staged optional digest match
  and no anomalies.
- `deprecated_md5_present` must be `true` when a `.md5` file appears in
  the staging directory; `false` otherwise.
- `paste_recipe` must be a non-empty string with the sha512sum / sha256sum
  verification commands.
- No extra keys are permitted in the response.
