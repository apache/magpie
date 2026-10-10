<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Pre-flight blocked

`reviewer-routing preflight` returned `verdict: blocked`. Show the maintainer each `blockers` entry and stop.

- **Privacy gate** — `privacy-llm-check` exited non-zero: the maintainer updates `<project-config>/privacy-llm.md` or runs `privacy-llm-check --list`, then re-runs.
- **No roster** — create `<project-config>/reviewer-roster.md` (template: [`reviewer-roster.md`](../../../../magpie-setup/templates/reviewer-roster.md)) or, for ASF projects, the rotations in `release-trains.md`.
- **Input** — ask for a valid `pr:<N>` or `issue:<N>`; never interpolate an unvalidated string into a read.
