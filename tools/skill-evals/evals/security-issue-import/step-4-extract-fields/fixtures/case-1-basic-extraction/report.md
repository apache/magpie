<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: "Maria Kovacs" <m.kovacs@bugresearch.example>
Subject: [SECURITY] Airflow Webserver: session cookie missing Secure flag

Hi,

The Airflow webserver sets the session cookie without the Secure flag, meaning
it can be transmitted over plain HTTP connections. An attacker with a
network-level position (e.g. coffee-shop WiFi) can intercept the cookie and
hijack an authenticated session.

Tested on Apache Airflow 2.9.0 and 2.9.3. I have not tested 2.10.x but the
relevant code appears unchanged in airflow/www/app.py.

Severity: Medium (CVSS 6.1 by my estimate)

Regards,
Maria
