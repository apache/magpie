<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with these fields:

- `decision`: `"declined"` or `"confirmed"`
- `policy_verified`: boolean; true only when the saved policy has been
  re-read and all required grants and applicable GitHub import labels are present.
- `policy_changed`: boolean; whether the saved policy actually changed.
- `stamp_written`: boolean; whether this skill was stamped clean.

Return no additional text.
