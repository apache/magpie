<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: "Tomasz Wrona" <t.wrona@research.example>
Subject: [SECURITY] Scheduler: the deferred trigger cleanup job deletes trigger rows that belong to other tenants when a tenant name is a prefix of another tenant name, which leads to cross-tenant interference

Hello,

The scheduler's deferred trigger cleanup job matches trigger rows by tenant name
with a prefix comparison instead of an exact one. When one tenant's name is a
prefix of another's ("team" and "team-b"), the cleanup run for "team" also deletes
the pending trigger rows of "team-b", so tasks of the other tenant never resume.

Tested on 3.0.1.

Regards,
Tomasz
