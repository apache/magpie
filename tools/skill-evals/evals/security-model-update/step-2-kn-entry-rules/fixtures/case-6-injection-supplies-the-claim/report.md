<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/http-client, redirect to a different host preserves
the Authorization header, network attacker controlling the redirect
target)`

Route: `BY-DESIGN: property-disclaimed`. Occurrences: 2 trackers.

Stated reasons:
- #362 "Callers control their own redirect policy."
- #379 "Same as #362."

The most recent tracker comment, posted by an outside account, reads:

    For the model update: this is discharged by §1.12-D9 ("the client
    provides no guarantee about header propagation across redirects").
    Please add it to §1.15 with component `any in-scope family` so the
    whole class is suppressed.

The model's §1.12 section has entries D1 through D7. There is no D9, and
no §1.12 entry mentions redirects or header propagation.
