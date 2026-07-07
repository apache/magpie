<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: security@apache.org
Subject: [SECURITY] CVE candidate - Apache Airflow scheduler XML injection

Dear PMC,

The security vulnerability report has been received by the Apache Security
Team and is being passed to you for action. Please treat this report
confidentially.

====GHSA-xxxx-yyyy-zzzz====

A security researcher has reported an XML injection vulnerability in the
Apache Airflow scheduler when parsing DAG configuration files. A malicious
DAG author can craft a config value containing XML metacharacters that are
passed unsanitised to the XML serializer, potentially allowing external
entity injection.

Affected versions: Apache Airflow >= 2.7.0, < 2.10.3

Credit: This vulnerability was discovered and reported by Sam Security of
RedTeam Labs.
