<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: "D. Park" <d.park@vulnlab.example>
Subject: Scheduler: pickle deserialization in XCom allows RCE (CVSSv3: 9.8 CRITICAL)

Hello,

I found that when the Airflow scheduler reads XCom values from the metadata
database, it uses pickle.loads() without validating the source. A user with
write access to the metadata database can store a crafted pickle payload and
trigger arbitrary code execution on the scheduler host.

Tested on Apache Airflow 2.10.0. The relevant code path is in
airflow/models/xcom.py orm_deserialize_value().

CVSS v3.1 Base Score: 9.8 (CRITICAL)
Vector: AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H

Regards,
D. Park
