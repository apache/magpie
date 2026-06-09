# SPDX-License-Identifier: Apache-2.0

## Context

Pre-flight check. The enabled list names an adapter that is not
installed on disk.

## Mock: project.md -> forwarders.enabled

```json
["platform-relay"]
```

## Mock: Installed adapters (tools/forwarder-relay/)

```json
["asf-security"]
```

## Mock: Inbound message

```
From: notifications@relay.example
Subject: [Relay] New report on Apache Airflow
Date: Mon, 2 Jun 2025 11:02:00 +0000
Message-ID: <relay-9931@relay.example>

A vulnerability has been reported via the relay platform for Apache Airflow.
```
