<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Receipt draft on the `maildir` backend

Read from [Step 7 item 4](../apply.md#step-7--apply-confirmed-imports).

On the `maildir` backend, file it per [*The Maildir backend*](../../../../../tools/gmail/draft-backends.md#the-maildir-backend) instead,
replying to the inbound report's `Message-ID`.

On `maildir`, the check is `maildir-draft-find` with the thread's `Message-ID`s instead.
If a pending draft already exists, surface it to the user instead of shadowing it with a second draft.
