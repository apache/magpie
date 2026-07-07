<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **import-path detection** step of the `security-issue-invalidate` skill.

A mock `gh issue view` response is provided below as the tracker state. Your job is to read the *Security mailing list thread* body field and classify the import path.

Return a JSON object with exactly these fields:

```json
{
  "import_path": "security_at_imported_public" | "security_at_imported_gmail_only" | "pr_imported" | "indeterminate",
  "email_draft_step": "required" | "skip" | "surface_to_user",
  "thread_id": "<string or null>",
  "rationale": "<one sentence>"
}
```

Field rules:
- `import_path`: one of the four enum values above.
  - `security_at_imported_public` — field contains a real URL (lists.apache.org or any other URL)
  - `security_at_imported_gmail_only` — field contains the exact sentinel `No public archive URL — tracked privately on Gmail thread <threadId>`
  - `pr_imported` — field contains the exact sentinel `N/A — opened from public PR <upstream>#<N>; no security@ thread`
  - `indeterminate` — field is empty, `_No response_`, or unrecognised
- `email_draft_step`: `required` for security@-imported paths; `skip` for pr_imported; `surface_to_user` for indeterminate.
- `thread_id`: the Gmail threadId string if extractable from the field (either the URL or the sentinel text), otherwise `null`.
- `rationale`: one sentence explaining the classification.
