<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base d4e5f6a)
Commits on branch: 2
Files changed: 2 (1 added, 1 modified)

Check results:
[
  {"category": "spdx_headers", "status": "fail", "details": "New file tools/my-helper/helper.py does not carry an SPDX-License-Identifier header in its first ten lines.", "locations": ["tools/my-helper/helper.py"]},
  {"category": "commit_shape", "status": "fail", "details": "Commit bcd2345 ('Added helper utility for hashing') uses past tense subject; imperative would be 'Add helper utility for hashing'.", "locations": ["bcd2345"]},
  {"category": "placeholder_convention", "status": "pass", "details": "", "locations": []},
  {"category": "contributing_conventions", "status": "pass", "details": "", "locations": []},
  {"category": "injection_guard", "status": "pass", "details": "", "locations": []}
]
any_blocking: true
