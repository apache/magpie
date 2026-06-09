# SPDX-License-Identifier: Apache-2.0

## Context

Pre-flight check. The enabled list, installed adapters, and message
are all valid; the skill should proceed to Step 1.

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
From: security@apache.org
Subject: [SECURITY] SSRF via HTTP operator callback URL
Date: Mon, 2 Jun 2025 09:14:22 +0000
Message-ID: <CABcde123@apache.org>

The Apache Security Team has received the following security report and
is forwarding it to the Airflow security list for triage.

Credit: Sam Researcher <s.researcher@infosec.example>
```
