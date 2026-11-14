<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-15 — Magpie changed since this project's last upgrade

**`code: "upgrade-pending"`** — the Magpie version running now
(`facts.to`) is not the one this project was last installed, configured
or upgraded to (`facts.from`). `facts.downgrade: true` means the running
version is the older one.

Before doing the work the user asked for, ask one question and wait for
the answer:

> Magpie changed since this project's last upgrade (`<from>` → `<to>`).
> Upgrade now with `/magpie-setup:upgrade` (`/magpie-setup-upgrade` on a
> snapshot install)? It checks this machine and this project, shows one
> plan, and changes nothing before you approve it. [yes / not now]

- **yes** → run the `setup-upgrade` skill now. When it finishes, carry on
  with the skill the user invoked, from its next pre-flight step.
- **not now** → carry on with the skill. Record nothing: the next skill
  asks again, and keeps asking until `setup-upgrade` records its run.

While this finding is present, an `isolated-setup-changed` or
`fingerprint-moved` finding in the same verdict is part of the same
upgrade: on **yes**, leave it to `setup-upgrade`; on **not now**, handle
it as its own section says.

Never run the upgrade without the **yes**, and never record its stamp
from here.
