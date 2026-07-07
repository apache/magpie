<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Skill name: security-report-importer
Purpose: Scans the private security@ Gmail inbox for unimported vulnerability
reports and creates draft tracking issues.

Data sources:
- Gmail API (via `mcp__claude_ai_Gmail`) — reads private emails sent to the
  project's security mailing list
- Email subject and body are reporter-supplied (externally controlled text)
- Attachments may include proof-of-concept code or log dumps

Writes:
- Creates a draft tracker issue via `gh issue create` with title and body
  populated from the email content
