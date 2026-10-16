<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — not a findings file

`security-management issue-import-from-md parse` exited `2` with `refused: not-a-findings-file`. From Step 0 item 3:

3. **The file is markdown of the expected shape.** Quick sanity
   check: at least one `# ` (title) heading and at least one
   `**Severity:**` metadata line. If neither is present, stop
   and surface: *"This does not look like a findings file. Expected
   format: per-finding `# Title`, `## Details`, `## Location`,
   `## Impact`, `## Reproduction steps`, `## Recommended fix`
   sections, then a `**Severity:** … **Status:** … **Category:**
   … **Repository:** … **Date created:** …` metadata block; blocks
   separated by `---` on their own line."*

The tool requires both a `# ` heading and a `**Severity:**` line, and at least one narrative block paired with a metadata block.
