<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Proposed PR body

Improve XCom value type handling in the extra links API by replacing the `pickle.loads()` call in `deserialize_value()` with `json.loads()`. This ensures only JSON-serializable values are accepted, preventing arbitrary object instantiation.

**Test plan:**
- [ ] `uv run --project airflow-core pytest tests/models/test_xcom.py -xvs`
- [ ] `prek run --from-ref main --stage pre-commit`

### Was generative AI tooling used to co-author this PR?

- [X] Yes — Claude Opus 4.6 (1M context)

Generated-by: Claude Opus 4.6 (1M context) following the guidelines at
https://github.com/apache/airflow/blob/main/contributing-docs/05_pull_requests.rst#gen-ai-assisted-contributions
