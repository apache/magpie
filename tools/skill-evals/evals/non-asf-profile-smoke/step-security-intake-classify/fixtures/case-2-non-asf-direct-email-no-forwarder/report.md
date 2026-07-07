<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config: Velox Stream (non-ASF community project)
  security_inbox.kind: ghsa-inbox
  forwarders.enabled: []
  cve_authority.tool: mitre-form
  governance.cve_allocation_gate: security-team-member

Direct vulnerability report sent to the project's public security contact
(no mailing-list forwarder relay; reporter found the contact in SECURITY.md):

From: researcher@bugbounty.example.com
To: security@velox-stream.example.io
Subject: SQL injection in velox-stream REST API parameter binding

Hello Velox Stream security team,

I found a SQL injection vulnerability in the REST API endpoint
`/api/v1/streams/search` when the `filter` parameter is not escaped
before it is interpolated into a raw SQL string.

Proof of concept:
  GET /api/v1/streams/search?filter='; DROP TABLE streams; --

Expected: the endpoint should use parameterized queries.
Actual: the raw filter value is interpolated into the query string,
allowing arbitrary SQL execution by any unauthenticated client.

This was tested against velox-stream 0.9.2 running with PostgreSQL 15.

Please let me know if you need more details.
