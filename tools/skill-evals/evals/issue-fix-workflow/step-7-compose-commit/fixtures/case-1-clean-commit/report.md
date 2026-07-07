<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError with bytes
Fix: added bytes pass-through in serialize_value()

Drafted commit message:
---
AIRFLOW-88101: allow bytes values in XCom.serialize_value()

serialize_value() unconditionally passed the value through json.dumps(),
raising TypeError when the caller stored a bytes object. The fix adds an
early-return path for bytes values so they are stored as-is without
JSON encoding.

Generated-by: Apache Magpie / issue-fix-workflow
---
