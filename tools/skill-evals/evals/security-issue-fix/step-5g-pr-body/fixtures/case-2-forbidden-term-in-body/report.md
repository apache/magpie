<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Proposed PR body

Fix security vulnerability in XCom deserialization. CVE-2025-44812 is addressed by replacing pickle.loads() with json.loads(). This prevents exploitation of the vulnerability by compromised workers.

**Test plan:**
- [ ] `uv run --project airflow-core pytest tests/models/test_xcom.py -xvs`

### Was generative AI tooling used to co-author this PR?

- [X] Yes — Claude Opus 4.6 (1M context)

Generated-by: Claude Opus 4.6 (1M context) following the guidelines at
https://github.com/apache/airflow/blob/main/contributing-docs/05_pull_requests.rst#gen-ai-assisted-contributions
