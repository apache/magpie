<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Command used:

```bash
skills/ci-runner-audit/scripts/scan_ci_runners.py all --repo-file /tmp/repos.txt --scope-name example-project --out-dir /tmp/ci-runner-audit --workers 20
```

Scope: two explicit repositories, default branches only.

`example-project-retired-gh-runners-confirmed.tsv`:

```tsv
repo  path  job  runner  html_url
apache/example  .github/workflows/ci.yml  build  ubuntu-20.04  https://github.com/apache/example/blob/main/.github/workflows/ci.yml
```

`example-project-macos-setup-action-arch-mismatches.tsv`:

```tsv
repo  path  job  runner  runner_arch  requested_arch  step  uses  evidence  html_url
apache/example  .github/workflows/build.yml  build  macos-latest  arm64  x64  Setup JDK  actions/setup-java@v5  with.architecture=x64  https://github.com/apache/example/blob/main/.github/workflows/build.yml
```

`example-project-macos-arch-mismatch-candidates.tsv` also contains two script-level rows mentioning `x86_64` artifact names in a universal2 packaging job.
