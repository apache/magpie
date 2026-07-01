<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# non-asf-profile-smoke evals

Smoke eval suite that drives skills through the
[`projects/non-asf-example/`](../../../../projects/non-asf-example/)
fixture profile and asserts that acceptance criterion 3 of
[`specs/project-agnosticism.md`](../../../../tools/spec-loop/specs/project-agnosticism.md)
holds:

> A non-ASF profile can be declared without editing any skill body.

Every case in this suite uses the same unmodified skill SKILL.md. The
`report.md` for each case carries non-ASF project config values and
asserts that the skill still produces correct output — demonstrating that
config substitution alone is sufficient across all tested surfaces.

## Suites (13 cases total)

| Suite | Skill tested | Step | Cases | What it covers |
|---|---|---|---|---|
| step-security-intake-classify | `security-issue-import` | Step 3 (classify) | 3 | non-ASF GHSA intake: direct advisory, direct email (no forwarder), automated-scanner noise — no ASF forwarder relay or mailing-list infrastructure required |
| step-release-backend-preflight | `release-prepare` | Step 0 (pre-flight) | 2 | non-ASF `github-releases` backend + `pr-approval` mechanism: clean pass and missing-train blocked |
| step-contributor-governance-intake | `committer-onboarding` | Step 1 (IP-compliance + comms) | 2 | non-ASF DCO model (`github-codeowners` governance) and no-CLA model (`maintainer-roster` governance): ICLA check skipped in both paths |
| step-1-fetch-pool | `issue-stale-sweep` | Step 1 (fetch candidate pool) | 3 | non-ASF GitHub Issues clean pass; framework-default fallback; component-filter selector |
| step-3-classify | `issue-stale-sweep` | Step 3 (classify each issue) | 3 | stale request-update; active skip; security-label skip (no ASF label names required) |

## What it proves

### Security intake (step-security-intake-classify)

- GHSA advisory notifications from `notifications@github.com` are
  classified as `Report` when the project uses `security_inbox.kind: ghsa-inbox`
  and `forwarders.enabled: []` — no ASF forwarder preamble required.
- Direct email reports to a non-ASF security contact address are correctly
  classified without requiring mailing-list infrastructure.
- Automated scanner output is correctly filtered as `automated-scanner`
  regardless of whether the project uses ASF or non-ASF infrastructure.

### Release backend (step-release-backend-preflight)

- The `release-prepare` pre-flight proceeds with `release_dist_backend:
  github-releases` and `release_approval_mechanism: pr-approval` — no
  `svnpubsub`, no `dev-list-vote`, no `announce@apache.org` required.
- A missing release-train entry blocks the pre-flight with the same
  blocker message regardless of the project's organization.

### Contributor governance (step-contributor-governance-intake)

- The `dco` intake model skips the ICLA check and Whimsy lookup, performs
  a DCO sign-off check against the candidate's merged PRs, and produces a
  congratulations email linking `committer_intake_dco.reference_url` — no
  ASF secretary account-request drafted.
- The `no-cla` intake model skips both ICLA and DCO checks and produces a
  congratulations email that includes the project's no-CLA explanation —
  no ASF secretary account-request drafted.

### Issue management (step-1-fetch-pool, step-3-classify)

- `step-1-fetch-pool` cases pass with `tracker_type: github-issues` and
  thresholds from a non-ASF `stale-sweep-config.md` — no `apache.org`
  fields, no PonyMail, no PMC roster required.
- `step-3-classify` cases pass using non-ASF label names (e.g.,
  `security-team` rather than the ASF default `security`) — the label
  name comes from `<project-config>/project.md → tracker.labels`, not
  from the skill body.

The SKILL.md file path in every `step-config.json` is identical to the
one used by the ASF eval suite — the same skill, different config.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/non-asf-profile-smoke/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/non-asf-profile-smoke/step-security-intake-classify/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/non-asf-profile-smoke/step-contributor-governance-intake/fixtures/case-1-dco-model-github-codeowners
```
