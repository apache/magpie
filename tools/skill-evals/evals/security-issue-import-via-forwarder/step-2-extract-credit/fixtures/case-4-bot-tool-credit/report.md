# SPDX-License-Identifier: Apache-2.0

## Context

Matched adapter: `asf-security`

The `asf-security` adapter's `extract_credit()` scans the body for a
`Credit:` line. Here the credited reporter is an automated scanner, so
the bot/AI credit policy applies and the credit kind is `tool`.

## Mock: Message body (passed to extract_credit)

```
The Apache Security Team has received the following security report and
is forwarding it to the Airflow security list for triage.

Credit: acme-security-bot <security-bot@acme.example>
GHSA: GHSA-aaaa-bbbb-cccc

--- Forwarded report below ---

Automated scan flagged a path-traversal in the DAG file processor that
allows reading files outside the configured DAGs folder.

Affected: Apache Airflow 2.10.x
```
