<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: carol@example.com
Subject: Authenticated admin can overwrite another user's connections

An Airflow admin user can modify connection records belonging to other users
via the Connections UI at /connection/edit. There is no ownership check —
any admin can overwrite any connection regardless of which user created it.
This could allow privilege escalation within a multi-tenant deployment.
