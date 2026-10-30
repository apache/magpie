<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# submit-to-oss-scan — the enrolment files, testing, and the PR body

Read from Steps 2–7 of [`SKILL.md`](../SKILL.md). The contract is
`anthropics/oss-scanner`'s README; re-read it on every run — where it and
this file disagree, the README wins. The worked example throughout is
[anthropics/oss-scanner#665](https://github.com/anthropics/oss-scanner/pull/665)
(a large Python workflow scheduler).

## Placement

| Where | Keys in `project.yaml` | Updates need | Names the programme in the project's repo |
|---|---|---|---|
| `projects/<name>/Dockerfile`, `projects/<name>/threat_model.md` | neither `dockerfile:` nor `threat_model:` | a PR to the scanner repo | no |
| `.oss-scanner/Dockerfile`, `.oss-scanner/threat_model.md` in `<upstream>` | `dockerfile:` and `threat_model:` set to those paths | a commit to `<upstream>` | yes |

Exactly one Dockerfile location; mixing (a file in both places, or a key
pointing at a missing file) fails `tools/validate.py`.

## project.yaml

Comment each key the way #665 did — the comments are the reviewer's
evidence that the values were chosen, not copied:

```yaml
# REQUIRED. The ONE git repository to scan, as an https:// URL. Optionally add #branch or #tag to pin one.
repo: https://github.com/<owner>/<repo>#<default-branch>

# REQUIRED. Who should we email our reports to, and use as the primary contact for questions.
# This is the address published in <link to SECURITY.md>
primary_contact: <security-list>

# Optional. The project's home page.
homepage: <url>

# Optional. true pauses reports without removing the enrolment; false (or omitting it) enables your project.
disabled: false

# The Dockerfile and threat_model.md are next to this file, so dockerfile: and threat_model: are omitted.
```

Every address is public. `auto_ccs:` adds recipients; `pgp:` (an armored
public key) encrypts reports but sends them to `primary_contact` only —
the two cannot be combined.

## Dockerfile

The scanner builds with the repository root as the context, **with**
network, then audits `/src` **without** it. What that requires:

1. **Base image** — the distribution and language version the project's
   own CI and reference images use (#665: `python:3.11-slim-bookworm`,
   because Airflow's CI and images run on Bookworm with 3.11 as default).
2. **System build dependencies** — copied from the CI image's own list,
   with a comment naming the script it came from, so it can be
   re-synced. Packages without wheels need their headers here.
3. **`COPY . /src` and `WORKDIR /src`** — the scanner contract.
4. **Pinned toolchain** — the version the repository pins (#665 reads the
   `uv` version out of `uv.lock`), not "latest".
5. **The full development environment** — every workspace package and
   test dependency, installed from the committed lock file
   (`uv sync --frozen --all-packages`, `npm ci`, `mvn dependency:go-offline` — never `-o` here, the build is the one step with network, …).
6. **Anything tests fetch lazily** — generate it now (#665 pre-generates
   `generated/provider_dependencies.json`, which the fixtures would
   otherwise download on first use).
7. **Freeze for offline** — environment variables that stop the toolchain
   re-resolving (`UV_FROZEN=1 UV_NO_SYNC=1 UV_OFFLINE=1`, the virtualenv on
   `PATH`; the equivalents for other ecosystems).
8. **A fast smoke slice** — a database-free test subset that proves the
   image works, and must not fail the build:
   `RUN <test command> || echo "WARNING: tests reported failures"`.
   End with a comment naming how to run further tests.

Do not add services the tests need at run time (a database server, a
broker) unless the project's CI starts them in-process; the audit runs one
container.

## threat_model.md

Derived from the security model — this is a summary for a scanner, not a
second model. Sections, in order:

1. **Pointer** — the authoritative model, its URL, and the section that
   lists what is not a vulnerability. "Read it before reporting."
2. **What the project does and where untrusted input enters** — the
   components and the entry points.
3. **Roles, most to least trusted** — and what each is trusted to do
   (#665: Deployment Managers, Dag authors, authenticated UI/API users by
   role, unauthenticated clients, workers with a scoped token).
4. **The defects we want found** — the boundary crossings, one bullet
   each, phrased as "*X* reaching *Y*".
5. **What is not a vulnerability** — the model's disclaimers and known
   non-findings (§1.12, §1.15), each **stated** in one line with its
   section cited. The audit runs offline: a link alone is unreadable, so
   an exclusion that is only linked does not exclude anything.
6. **Severity guidance** — the project's rating reference
   (`<project-config>/security-model.md` → *Severity-rating reference*),
   plus where the team draws lines (e.g. authenticated-only, needs a
   non-default setting, Dag-author-only).
7. **How reports and patches should look** — reproducer expectations,
   the patch style, where tests go.

Last line: `Derived from <model URL> at commit <sha>.` — the last commit that
touched the model file, not a date: two amendments in one month must
still be told apart.
Every bullet must trace to a model section; a bullet that does not is a
model gap (`security-model-update`), not a line to write here.

## Testing before the PR

In the maintainer's fork of `anthropics/oss-scanner`, with the files in
`projects/<name>/`; the host needs git, Docker, Python 3 and PyYAML.

```bash
python3 tools/validate.py                 # schema and placement rules
tools/check <name>                        # build the scanner's way, then a shell with no network
# inside that shell:
<the smoke slice from the Dockerfile>
<one deeper test path, e.g. uv run pytest <package>/tests/unit -q>
tools/check --qemu <name>                 # optional: scanner-shaped VMs (Linux x86-64 with QEMU)
```

`tools/check` runs the Dockerfile with network access and installs Claude
Code into the image, as the scanner does — use a machine with nothing to
lose. Failures seen in practice and their usual cause:

| Symptom inside the offline shell | Cause | Fix in the Dockerfile |
|---|---|---|
| The toolchain tries to resolve or download | not frozen | the step-7 environment variables |
| A fixture fails on first use with a network error | lazily fetched data | generate it at build time (step 6) |
| Build fails compiling a dependency | missing system headers | sync the CI image's package list (step 2) |
| Tests need a database or broker | external service | run the database-free slice; note it in `threat_model.md`'s testing section |

## PR body

The `anthropics/oss-scanner` pull-request template's checklist, each box
ticked only on the maintainer's confirmation, then a context paragraph.
#665's checklist:

```markdown
## Enrol `projects/<name>`

I have verified each of the following before submitting this project:

- [ ] I am a core maintainer of this project.
- [ ] I accept the [OSS Scanner terms](https://red.anthropic.com/oss-scanner/terms/).
- [ ] I confirm that I believe my project meets the inclusion criteria and is an established project that users depend on.
- [ ] `project.yaml` follows the README (one project per PR; `tools/validate.py` passes locally).
- [ ] `tools/check <name>` builds the project, and its tests run in the shell that follows.
- [ ] `primary_contact` must be the email address of the primary security contact.
- [ ] There is a `Dockerfile` that builds the project (required) in one of two places: …
- [ ] `threat_model.md` is written for this project (recommended but optional), placed in the same way: …

Context: <what the project is and who depends on it>. <The submitter's role in the project and its security team>.
`primary_contact` is the project's private security list published in <SECURITY.md link>.
The threat model summarises <project>'s security model (<URL>), which lists what the project does not treat as a vulnerability.
```

Use the template as it is on the scanner repo's default branch at the time
of the run, not this copy. After opening, an automated triage comment
tabulates eligibility signals; answer any warning it raises (as #665 did
for the OSS-Fuzz contact) with a drafted reply the maintainer approves.
