<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Tools

PonyMail MCP is enabled and authenticated; `mcp__ponymail__save_attachments` is available (root `/home/t/.cache/ponymail-attachments`).

## Root message (mid `x7k2pq`, thread `19a3f0`)

From: "OSS Scan Service" <reports@oss-scan.example>
Subject: Path traversal in the log viewer endpoint

The reproducer is in the attached archive. To keep mail filters from
stripping it, the archive is password protected; the password is
`grey-Heron-42`.

## Previous save_attachments result

- poc.zip
  application/zip, 4120 bytes, sha256 9a1f…
  archive: zip (encrypted)
  not extracted: call again with `password` (usually given in the report text)
