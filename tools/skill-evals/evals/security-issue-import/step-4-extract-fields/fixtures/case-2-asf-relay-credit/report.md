<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: security@apache.org
Subject: [SECURITY] CVE candidate - Apache Airflow providers SMTP: cleartext credential logging

Dear PMC,

The security vulnerability report has been received by the Apache Security
Team and is being passed to you for action. Please treat this report
confidentially.

====GHSA-8vqj-3m2k-np4x====

The SMTP provider hook logs the full SMTP URL including credentials at DEBUG
level. Any operator with access to task logs (a common default in multi-tenant
deployments) can read connection passwords in plain text.

Affected: Apache Airflow >= 2.6.0, < 2.10.2 (providers.smtp >= 1.0.0)

Credit: This vulnerability was discovered and reported by Jordan Lee of
Horizon Security Research.
