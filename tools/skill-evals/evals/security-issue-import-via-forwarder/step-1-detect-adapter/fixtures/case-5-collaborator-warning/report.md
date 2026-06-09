# SPDX-License-Identifier: Apache-2.0

## Context

A relay-shaped message arrives from an address that matches the
adapter's (broad) sender pattern but also belongs to a project
collaborator on the security team. The adapter still matches, but the
self-check should raise a collaborator warning for the human reviewer.

## Mock: Registered adapters (forwarders.enabled)

```json
[
  {
    "name": "asf-security",
    "sender_pattern": ".*@apache\\.org",
    "preamble_match": "The Apache Security Team has received"
  }
]
```

## Mock: Project collaborator list (security team)

```json
["j.security-member@apache.org", "a.committer@apache.org"]
```

## Mock: Inbound message

```
From: j.security-member@apache.org
Subject: Re: [SECURITY] follow-up on operator SSRF
Date: Mon, 2 Jun 2025 14:05:00 +0000
Message-ID: <CABxyz789@apache.org>

The Apache Security Team has received the following security report and
is forwarding it to the Airflow security list for triage.

Credit: External Reporter <ext@infosec.example>
```
