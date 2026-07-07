<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError with bytes

Drafted commit message:
---
AIRFLOW-88101: allow bytes values in XCom.serialize_value()

Adds early-return for bytes inputs in serialize_value().
---
