# SPDX-License-Identifier: Apache-2.0

## Context

Pre-flight check. The in-hand message is missing its `From:` header,
so it is not a structurally valid relay message.

## Mock: project.md -> forwarders.enabled

```json
["asf-security"]
```

## Mock: Installed adapters (tools/forwarder-relay/)

```json
["asf-security"]
```

## Mock: Inbound message

```
Subject: [SECURITY] Possible deserialization issue
Date: Mon, 2 Jun 2025 12:30:00 +0000

The Apache Security Team has received the following security report and
is forwarding it to the Airflow security list for triage.
```
