<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Tracker discussion context

**Collaborators (tracker write access):** triager-a, triager-b, triager-c

**Comment from @triager-b (collaborator):**
> The fix is straightforward. In `airflow/models/xcom.py` at `deserialize_value()`, replace the `pickle.loads(value)` call with:
> ```python
> import json
> return json.loads(value)
> ```
> This enforces type-safe deserialization.

**Files to change:**
- `airflow/models/xcom.py` — replace `pickle.loads()` with `json.loads()` in `deserialize_value()` at line 312.
