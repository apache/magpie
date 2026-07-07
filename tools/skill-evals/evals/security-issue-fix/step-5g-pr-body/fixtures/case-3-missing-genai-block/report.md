<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Proposed PR body

Improve XCom value type handling by replacing pickle.loads() with json.loads() in deserialize_value(). This tightens the type contract and prevents unexpected object instantiation from stored XCom values.

**Test plan:**
- [ ] `uv run --project airflow-core pytest tests/models/test_xcom.py -xvs`
- [ ] `prek run --from-ref main --stage pre-commit`
