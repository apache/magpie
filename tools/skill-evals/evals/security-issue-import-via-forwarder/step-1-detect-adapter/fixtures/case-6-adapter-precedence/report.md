# SPDX-License-Identifier: Apache-2.0

## Context

Two adapters are enabled and the inbound message could match either
one (the asf sender pattern AND the platform-relay preamble are both
present). The first adapter in enabled order whose detect() returns
non-null wins; later adapters are skipped.

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
From: security@apache.org
Subject: [SECURITY] forwarded platform report
Date: Mon, 2 Jun 2025 15:20:00 +0000
Message-ID: <CABprec01@apache.org>

The Apache Security Team has received the following security report and
is forwarding it to the Airflow security list for triage.

A vulnerability has been reported via the relay platform for Apache Airflow.
```
