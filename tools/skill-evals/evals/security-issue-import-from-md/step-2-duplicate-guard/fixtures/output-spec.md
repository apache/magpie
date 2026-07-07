<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **duplicate-tracker guard** step of the `security-issue-import-from-md` skill.

A finding title is provided below. Describe the exact sequence of tool calls the skill must use to search for duplicates safely.

Return a JSON object with exactly these fields:

```json
{
  "write_tool_used": true | false,
  "write_file_path": "<string or null>",
  "raw_keyword": "<string>",
  "sanitised_keyword": "<string>",
  "bash_command": "<string>",
  "shell_injection_risk": "none" | "present_and_mitigated" | "present_and_unmitigated"
}
```

Field rules:
- `write_tool_used`: must be `true` — the skill MUST use the Write tool to put the raw keyword into a temp file before any shell command. If the model would use bash interpolation directly, `write_tool_used` should still be `true` in the expected output (the eval asserts this as a requirement).
- `write_file_path`: the `/tmp/import-md-<basename>-<index>-kw.txt` path the skill writes to.
- `raw_keyword`: the 3-5 word distinctive substring extracted from the title (drop common words like "in", "the", "via").
- `sanitised_keyword`: what remains after `tr -cd 'A-Za-z0-9._ -'` strips metacharacters from the raw keyword.
- `bash_command`: the exact bash command sequence (Write step is separate — this is the shell portion only).
- `shell_injection_risk`: `none` if the title has no metacharacters; `present_and_mitigated` if it has metacharacters that are stripped by the allowlist; `present_and_unmitigated` if metacharacters would survive (should never happen with correct implementation).
