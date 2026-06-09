# SPDX-License-Identifier: Apache-2.0

## Context

Pre-flight check for the via-forwarder skill. The adopter runs no
forwarder layer at all.

## Mock: project.md -> forwarders.enabled

```json
[]
```

## Mock: Installed adapters (tools/forwarder-relay/)

```json
["asf-security"]
```

## Mock: Inbound message

```
From: security@apache.org
Subject: [SECURITY] SSRF via HTTP operator callback URL
Date: Mon, 2 Jun 2025 09:14:22 +0000
Message-ID: <CABcde123@apache.org>

The Apache Security Team has received the following security report and
is forwarding it to the Airflow security list for triage.
```
