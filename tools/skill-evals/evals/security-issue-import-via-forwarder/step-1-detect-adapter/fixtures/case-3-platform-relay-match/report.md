# SPDX-License-Identifier: Apache-2.0

## Mock: Registered adapters (forwarders.enabled)

```json
[
  {
    "name": "asf-security",
    "sender_pattern": "security@apache.org",
    "preamble_match": "The Apache Security Team has received"
  },
  {
    "name": "platform-relay",
    "sender_pattern": "notifications@relay.example",
    "preamble_match": "A vulnerability has been reported via the relay platform"
  }
]
```

## Mock: Inbound message

```
From: notifications@relay.example
Subject: [Relay] New vulnerability report: Path traversal in Airflow task log viewer
Date: Wed, 4 Jun 2025 08:32:00 +0000
Message-ID: <relay-98765@relay.example>

A vulnerability has been reported via the relay platform for Apache Airflow.

Reporter: Maria Security-Hunter
Report URL: https://relay.example/reports/12345

--- Report body ---

The task log viewer endpoint does not sanitise the `dag_id` or `task_id`
path components, allowing an authenticated attacker to traverse the file
system using `../` sequences.

Affected versions: 2.9.x, 2.10.x
```
