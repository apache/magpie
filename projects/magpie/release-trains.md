<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie: release trains](#apache-magpie-release-trains)
  - [Trains](#trains)
  - [Releases](#releases)
  - [Release Manager roster](#release-manager-roster)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie: release trains

Release-train identity and the Release Manager roster the release
skills (and the security family) read. Template:
[`projects/_template/release-trains.md`](../_template/release-trains.md).

## Trains

Magpie is pre-1.0 and runs a **single active train** off `main`. There
is no maintenance/backport line yet; that convention is added here when
the first `X.Y` line needs one.

| Train | Branch | Status | Supported |
|---|---|---|---|
| `0.x` | `main` | active | latest `0.x` release only |

## Releases

| Version | Train | Release Manager | Notes |
|---|---|---|---|
| `0.1.0` | `0.x` | Jarek Potiuk (`potiuk`) | First Apache Magpie release. |

## Release Manager roster

Any PMC member may serve as Release Manager. The RM for a given release
is recorded in the *Releases* table above. Jarek Potiuk (`potiuk`),
PMC Chair, is the RM for the first release; RM assignment for
subsequent releases rotates per PMC agreement.

The RM's signing-key fingerprint is **not** stored here — it lives in
the RM's personal `user.md` (`release_manager.gpg_fingerprint`), and
the public half must appear in the project
[`KEYS`](https://dist.apache.org/repos/dist/release/magpie/KEYS) file
and be registered in the ATR platform before the RC is cut.
