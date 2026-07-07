<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError with bytes

Drafted commit message:
---
Allow bytes values in XCom serialization

serialize_value() now handles bytes inputs correctly.

Generated-by: Apache Magpie / issue-fix-workflow
---
