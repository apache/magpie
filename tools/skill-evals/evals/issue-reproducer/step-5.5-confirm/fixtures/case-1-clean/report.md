<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101 — XCom.set() TypeError
Reporter: alice-dev

Adapted reproducer:
  from airflow.models import XCom

  XCom.serialize_value(b"bytes")
