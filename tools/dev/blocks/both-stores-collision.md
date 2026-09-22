<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

A `skills` entry for the same skill in both stores is an expected
transitional state, not a fault — it needs no hand edit and no bug to
produce. It is what the ordinary config-then-adopt path produces
across two machines: a contributor
runs `config` on their machine before the project adopts, a
maintainer runs `adopt` on a different machine, and `adopt` can only
migrate the local stamp it can see — so the contributor's local
entry survives beside the newly committed one. When it happens, the
local entry wins for every comparison, and `/magpie-setup reconcile`
names the collision and offers to drop the redundant local entries,
leaving the committed lock as the single store.
