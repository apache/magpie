# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Step 7 item 4: whether a confirmed import gets a receipt-of-confirmation draft.

The matrix, first match wins:

| Condition | Draft | Recorded |
|---|---|---|
| class `Report (disposition converged)` | none | converged note in the rollup |
| `reporter_acknowledgement_model: none` | none | suppression in the rollup, a recap note |
| part of a consolidated-receipt bundle | none (the bundle covers it) | the bundle's draft id in the rollup |
| `manual` | the canned receipt, for triager review | — |
| `auto` | the same receipt, summary tagged `[auto-ack]` | — |

`window_days` is echoed for the receipt's CVD-deadline wording. A
forwarder-relayed candidate's draft is routed through the via-forwarder
sub-skill's Step 3. Nothing is ever sent: `[auto-ack]` is a hint to the
triager, not an instruction to dispatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.issue_import.governance import DEFAULT_MODEL, DEFAULT_WINDOW_DAYS, MODELS

CONVERGED = "Report (disposition converged)"
FORWARDER = "forwarder-relayed"
SUPPRESSED_NONE = (
    "acknowledgement_model=none: receipt-of-confirmation draft suppressed per "
    "<project-config>/security-intake-config.md disclosure_governance"
)
RECAP_NONE = "acknowledgement_model=none: no receipt-of-confirmation draft created for this candidate"
AUTO_TAG = "[auto-ack]"
AUTO_NOTE = (
    "acknowledgement_model=auto — this is the standard receipt template and may be sent without further "
    "triager review per your project's security-intake-config.md disclosure_governance"
)


def decide(data: Mapping[str, Any]) -> dict[str, Any]:
    """`data`: class, model, window_days, bundle_draft_id, converged_ref."""
    klass = str(data.get("class") or "Report")
    model = str(data.get("model") or DEFAULT_MODEL)
    if model not in MODELS:
        raise ValueError(f"reporter_acknowledgement_model {model!r} is not one of {', '.join(MODELS)}")
    window = int(data.get("window_days") or DEFAULT_WINDOW_DAYS)
    result: dict[str, Any] = {
        "draft_created": False,
        "draft_auto_ack_tagged": False,
        "suppressed_reason": None,
        "rollup_note": None,
        "rollup_receipt": {},
        "proposal_note": None,
        "route": "via-forwarder" if klass == FORWARDER else "direct",
        "window_days": window,
    }
    if klass == CONVERGED:
        result["rollup_receipt"] = {"converged": True, "converged_ref": data.get("converged_ref")}
        return result
    if model == "none":
        result["suppressed_reason"] = SUPPRESSED_NONE
        result["rollup_note"] = RECAP_NONE
        result["rollup_receipt"] = {"suppressed_reason": SUPPRESSED_NONE}
        return result
    if data.get("bundle_draft_id"):
        result["rollup_receipt"] = {"bundle_draft_id": data["bundle_draft_id"]}
        return result
    result["draft_created"] = True
    if model == "auto":
        result["draft_auto_ack_tagged"] = True
        result["auto_ack_tag"] = AUTO_TAG
        result["proposal_note"] = AUTO_NOTE
    return result
