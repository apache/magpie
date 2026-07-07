<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`sandbox-lint`](#sandbox-lint)
  - [Prerequisites](#prerequisites)
  - [What it checks](#what-it-checks)
  - [How to use](#how-to-use)
  - [CI wiring](#ci-wiring)
  - [Updating the baseline](#updating-the-baseline)
  - [Residual risk](#residual-risk)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `sandbox-lint`

**Capability:** substrate:sandbox

**Harness:** Claude Code, OpenCode

Lints `.claude/settings.json` against the shipped baseline at
`tools/sandbox-lint/expected.json`, and against the security
invariants documented in `docs/security/threat-model.md`
(mitigation **M.29**). The threat-model document lands in a
companion PR; the lint stands on its own and runs immediately on
merge.

**OpenCode.** `--opencode opencode.json` lints the other harness's
security config. OpenCode has no `sandbox.filesystem` allow/deny model
(its filesystem isolation comes from the OS-level sandbox of the
secure-agent setup), so there is no baseline to diff — instead the lint
asserts **invariants on the `permission` policy**
([OpenCode permissions](https://opencode.ai/docs/permissions/)): the
policy must not be a blanket `"allow"`, `permission.bash` must not default
to `"allow"`, no rule may auto-approve a dangerous command family
(`git push`, `sudo`, `curl`/`wget`, `rm -rf`, cloud CLIs, `kubectl`,
`docker run`, `ssh`, interpreters, …) via last-match-wins evaluation, and
`webfetch` / `external_directory` must not be blanket-`"allow"`.

```bash
uv run --project tools/sandbox-lint sandbox-lint --opencode opencode.json
```

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (stdlib only, no third-party deps).
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline/local — it only reads local JSON files.

## What it checks

1. **Baseline parity.** Every key/value in the live settings file
   must match the baseline. Lists tagged as set-typed (`denyRead`,
   `allowRead`, `allowWrite`, `allowedDomains`, `excludedCommands`,
   `deny`, `ask`) are
   compared as sets so a re-order does not trip the lint, but every
   addition or removal does. Any drift fails CI.
2. **Hard invariants.** Independent of the baseline, the live
   settings must satisfy the security boundaries the threat model
   commits to:
   - `sandbox.enabled` is `true`.
   - `sandbox.filesystem.denyRead` contains `~/`.
   - `sandbox.filesystem.allowRead` contains no credential or root
     paths (`~/.aws`, `~/.ssh`, `~/.netrc`, `~/.docker`, `~/.kube`,
     `~/.azure`, `~/.config/gcloud`, `/`, `~/`).
   - `sandbox.filesystem.allowWrite` is a subset of `allowRead` and
     contains no credential, config-root, or homedir-root path.
   - `permissions.deny` contains the verbatim entries listed in
     [`src/sandbox_lint/__init__.py`](src/sandbox_lint/__init__.py)
     (`REQUIRED_PERMISSIONS_DENY`).
3. **Baseline self-check.** The same invariants are applied to
   `expected.json` itself, so a PR cannot weaken the baseline in
   lockstep with the live settings without the lint catching the
   underlying boundary violation.

## How to use

Run from the repository root:

```sh
uv run --directory tools/sandbox-lint --group dev sandbox-lint
```

Run with explicit paths (useful for tests):

```sh
uv run --directory tools/sandbox-lint --group dev sandbox-lint \
  --settings .claude/settings.json \
  --expected tools/sandbox-lint/expected.json
```

Exit code is `0` on a clean pass, `1` on any invariant violation or
baseline drift.

## CI wiring

The lint runs in two places:

- The
  [`sandbox-lint`](../../.github/workflows/sandbox-lint.yml)
  GitHub Actions workflow, on every PR that touches
  `.claude/settings.json`, the baseline, or the lint code itself.
- The repository's `prek` config
  ([`.pre-commit-config.yaml`](../../.pre-commit-config.yaml)) runs
  `pytest`, `ruff check`, `ruff format --check`, and `mypy` against
  this project, so contributors hit the same checks locally.

## Updating the baseline

Any legitimate edit to `.claude/settings.json` must be paired with
the same edit to `tools/sandbox-lint/expected.json` in the same PR.
This is the explicit acknowledgement that mitigation M.29 requires:
two files, two edits, one review surface. The lint refuses to pass
if the two diverge.

## Residual risk

A maintainer running an agent locally can edit `.claude/settings.json`
to weaken the sandbox without ever opening a PR. This lint catches
the *shipped* configuration but not local overrides during a single
agent run. The companion threat-model document records this under
section *X3, Sandbox bypass via developer override* and *Residual
risk #4*; consult that document once it lands on `main`.
