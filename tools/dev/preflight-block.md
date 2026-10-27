<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently.
One command answers it and carries its own rules; there is nothing else to
read.

Run the checker with this skill's own frontmatter `name:` and
`surface_hash:`, and one `--requires` for each `requires_config:` entry:

```bash
PYTHONPATH="$(git rev-parse --git-common-dir 2>/dev/null || { test -e .git || { test -f .svn/wc.db && echo .svn; }; })/apache-magpie" \
  python3 -P -m setup_preflight --skill <name> --hash <surface_hash> [--requires <file>]...
```

The path finds the checker `/magpie-setup:setup config` installed in the
git directory's `apache-magpie/` (`.svn/apache-magpie/` in a Subversion
working copy). Pre-flight imports the checker only from paths a
repository cannot commit: `-P` keeps the working tree off the import
path, and no in-tree directory is on it. Never add one.

- **`{"verdict": "ok"}`** → **silent**. Continue into the work the user
  asked for and say nothing about pre-flight. This is the ordinary answer.
- **`{"verdict": "action", ...}`** → each finding names a section, and
  `rules` carries that section's text. Follow it. The `facts` are the
  inputs; what to propose, and what may not be done, are in the rules
  rather than here. **Act on a finding only through its rules.**
- **The command did not run at all** — no such module, a non-zero exit, no
  `python3` 3.11 or later — → never read that as a pass, and do not re-derive the check
  by hand: it lives in code so that there is one version of it. If the
  project has **no** `.apache-magpie.lock`, `.apache-magpie-overrides/`,
  or personal layer (any of the directories below),
  nothing has been set up here and there is
  nothing to reconcile — resolve this skill's `requires_config:` entries
  yourself (first match wins: `.apache-magpie-local/<file>`, the main
  checkout's `.apache-magpie-local/<file>`, `<git-common-dir>/apache-magpie/<file>`,
  `.svn/apache-magpie/<file>`, then `.apache-magpie-overrides/<file>`), stay silent if they all resolve, and
  run `/magpie-setup:setup config` for this skill if any does not, which also
  installs the checker. With no version control there is no checker, by
  design: resolve the entries the same way. Otherwise the project *is* set up and its checker
  is missing or stale: say so, propose `/magpie-setup:setup config` to install
  it or `/magpie-setup:setup upgrade` to refresh it, and carry on with the work.

**Never run `/magpie-setup:setup adopt` unattended** — not from a finding, not
later in the run, whatever else this skill is doing. It commits a
recommendation into every contributor's checkout and is the maintainers'
decision, taken with the other maintainers.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup:setup verify` is the full diagnostic.
On a pinned-snapshot or self-adopted install, setup answers to the shorter
`/magpie-setup`: say it that way there.
