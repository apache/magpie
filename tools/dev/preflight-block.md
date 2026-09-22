<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently.
One command answers it; the rules for anything it reports live in
`preflight-detail.md`, in this skill's own directory, beside this file.

Run the checker with this skill's own frontmatter `name:` and
`surface_hash:`, and one `--requires` for each `requires_config:` entry:

```bash
PYTHONPATH=.apache-magpie-local python3 -m setup_preflight \
  --skill <name> --hash <surface_hash> [--requires <file>]...
```

- **`{"verdict": "ok"}`** → **silent**. Continue into the work the user
  asked for and say nothing about pre-flight. This is the ordinary answer.
- **`{"verdict": "action", "findings": [...]}`** → for each finding, read
  the `preflight-detail.md` section its `section` field names and follow
  it. The `facts` are the inputs; what to propose, and what may not be
  done, are there rather than here. **Do not act on a finding without
  reading its section.**
- **The command did not run at all** — no such module, a non-zero exit, no
  `python3` — → never read that as a pass. If the project has **no**
  `.apache-magpie.lock`, `.apache-magpie-local/` or
  `.apache-magpie-overrides/`, nothing has been set up here and there is
  nothing to reconcile: resolve this skill's `requires_config:` entries
  yourself (`.apache-magpie-local/<file>` first, then
  `.apache-magpie-overrides/<file>`), stay silent if they all resolve, and
  run `/magpie-setup config` for this skill if any does not — that also
  installs the checker. Otherwise the project *is* set up and the checker
  is missing or broken → read *step-0* in `preflight-detail.md`.

**Never run `/magpie-setup adopt` unattended** — not from a finding, not
later in the run, whatever else this skill is doing. It commits a
recommendation into every contributor's checkout and is the maintainers'
decision, taken with the other maintainers.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic.
