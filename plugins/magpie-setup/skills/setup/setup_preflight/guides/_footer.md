<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## 👋 About this guide

- **Continue** — show it again next time (three times at most)
- **Dismiss** — hide it until the next Magpie upgrade
- **Don't show again** — hide it for good; say *"show the {{label}} welcome again"* to bring it back

Show this again any time: `/magpie-setup:welcome-guide{{arg}}`
(`/magpie-setup-welcome-guide{{arg}}` on a pinned snapshot).

🌈 Prefer it in colour? Run this yourself — the `!` prefix runs it as a shell command:

```text
! PYTHONPATH="$(git rev-parse --git-common-dir 2>/dev/null || { test -e .git || { test -f .svn/wc.db && echo .svn; }; })/apache-magpie" python3 -P -m setup_preflight.welcome show --family {{guide}} --color=always
```
