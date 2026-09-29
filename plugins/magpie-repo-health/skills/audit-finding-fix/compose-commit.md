<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Compose the commit

Companion to [`SKILL.md`](SKILL.md). The commit-message convention and the hand-back artefact contents for Step 6.

Write the commit message per the project's convention:

- **Subject** — `fix(<area>): address <tool> findings in <files>`
  (or per the project's `<project-config>/fix-workflow.md`).
  Do not include rule codes in the subject unless the project's
  convention requires them — they belong in the body.
- **Body** — one paragraph: which tool, how many findings, the
  rules addressed, and a one-sentence summary of the fix strategy.
  No security language.
- **Trailer** — the trailer the repository's commit-attribution convention names, resolved per [`commit-attribution.md`](../../../../docs/setup/commit-attribution.md) (`Generated-by: <tool-name>` by default),
  added with `git commit --trailer "<trailer>"` per the
  [`AGENTS.md` → *Commit and PR conventions*](../../../../AGENTS.md#commit-and-pr-conventions).
  The trailer is the contributor's call on their own commit; the
  skill does not add it to anyone else's commit.

Show the commit message to the user; ask for confirmation before
running `git commit`.

**Signing pre-flight.** If `commit.gpgsign` is true, probe the
gpg-agent cache before running `git commit` — a token-backed
signing key with a cold cache blocks on a pinentry prompt the
agent cannot see, and the commit dies with
`gpg: signing failed: Timeout` after a long stall. On a cold
cache, surface a dialogue telling the user to expect the prompt
(or hand them the command to run in their own terminal); on a
warm cache, commit without interrupting them. The probe and the
rationale are in
[`AGENTS.md` → *Commit and PR conventions*](../../../../AGENTS.md#commit-and-pr-conventions).

Return ONLY valid JSON with this structure:

```json
{
  "subject": "<proposed commit subject line>",
  "body_ok": true | false,
  "security_language_present": true | false,
  "trailer_present": true | false,
  "trailer_key": "Generated-by" | null
}
```

`security_language_present` is true if the subject or body
contains: "CVE", "vulnerability", "security fix", "security
patch", "exploit", or similar security-framing terms.

---
