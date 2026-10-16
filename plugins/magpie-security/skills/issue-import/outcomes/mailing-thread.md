<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — the *Security mailing list thread* field

Read from the [Step 4 field table](../SKILL.md#step-4--extract-template-fields) and Step 7 item 1.
The heading is the project's `tracker.body_fields.mailing_thread` when it declares one; the value is the same either way.

Keep the private thread handle and, if possible, the PonyMail archive link. Construct the search URL per [`tools/gmail/ponymail-archive.md`](../../../../../tools/gmail/ponymail-archive.md#use-case--security-issue-import) (the project's template is in [`project.md`](../../../../../<project-config>/project.md#gmail-and-ponymail)), propose it at Step 5, and wait for the user to paste back the resolved `<mail-archive-url>/thread/<hash>?<security-list>` URL. Record that URL, the Gmail `threadId`, **and the root `Message-ID`**: unlike a `threadId`, which resolves only in one mailbox, the `Message-ID` finds the report from any account. Resolve it per [`tools/gmail/operations.md`](../../../../../tools/gmail/operations.md#get-the-root-message-id-of-a-thread) (PonyMail returns it; on Gmail use the `oauth-draft-message-id` helper), and record it as ``Root Message-ID: `<id>` ``: **backtick-wrapped**, since a bare `<...@...>` renders as an HTML tag. The field is **internal-only**: `generate-cve-json` never exports it to `references[]` (see "CVE references must never point at non-public mailing-list threads" in [`AGENTS.md`](../../../../../AGENTS.md)).

Until the archive URL is pasted back, the value is:

```text
No public archive URL — tracked privately on Gmail thread `<threadId>`.
Root Message-ID: `<root-message-id>`
```
