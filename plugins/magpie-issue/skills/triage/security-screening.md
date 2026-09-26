<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security screening before any public comment

Companion to [`SKILL.md`](SKILL.md). Body of Golden rule 8: the
security-signal scan and the stop-and-warn flow required before
composing any public triage comment.

The `security_committers` policy forbids public
disclosure of an undisclosed security vulnerability. Before
composing any proposal comment, the skill checks the issue body
and comments for signals that the report may describe a security
vulnerability: mentions of remote code execution, authentication
bypass, privilege escalation, credential or secret exposure, CVE
/ CVSS references, JNDI / SQL / shell injection, or language
suggesting the reporter is withholding details pending coordinated
disclosure. If any signal is found, **stop the normal flow** — do
not draft or post a public comment. Instead surface a warning to
the user:

> "This issue may describe a security vulnerability. Do **not**
> post a public triage comment. Route privately to
> `security@<project>.apache.org` per the ASF Security Committers
> policy. Only continue the normal triage flow if you have
> confirmed the issue is not a security vulnerability."

The user must explicitly confirm the issue is *not*
security-sensitive before the six-class classification flow may
continue.
