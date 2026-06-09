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
From: independent.researcher@gmail.com
Subject: SQL injection in Airflow REST API filter parameter
Date: Tue, 3 Jun 2025 14:05:11 +0000
Message-ID: <XYZabc789@gmail.com>

Hello,

I discovered a SQL injection vulnerability in the /api/v1/dags endpoint
when the `filter_tags` parameter is passed without sanitisation.

Reproduction:
  GET /api/v1/dags?filter_tags=1' OR '1'='1

This affects Airflow 2.10.0 and earlier.

Best,
Independent Researcher
```
