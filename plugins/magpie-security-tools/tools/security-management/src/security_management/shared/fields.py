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
"""Read template fields out of an existing tracker body, fail closed.

The one reader is github-body-field: the body is normalised in memory
against the template headings, then each field is extracted. A field the
normaliser will not decide on (repeated with different values, or a heading
markdown readers could disagree on) is reported under `undecided`, never
guessed and never read as empty. A field that is absent, or holds
`_No response_`, reads as `""`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from github_body_field import parser as gbf

from security_management.shared import body


def read(
    text: str,
    roles: Iterable[str],
    body_fields: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """`{values: {role: str}, absent: [role], undecided: [{role, field, kind, lines}]}`."""
    headings = body.headings(body_fields)
    normalised = gbf.normalise(text, list(headings.values()))
    values: dict[str, str] = {}
    absent: list[str] = []
    undecided: list[dict[str, Any]] = []
    for role in roles:
        heading = headings[role]
        decision = next((d for d in normalised.needs_decision if d["field"] == heading), None)
        if decision is not None:
            undecided.append(
                {"role": role, "field": heading, "kind": decision["kind"], "lines": decision.get("lines")}
            )
            continue
        try:
            value = gbf.extract_field(normalised.text, heading).strip()
        except (gbf.AmbiguousFieldError, gbf.DuplicateFieldError) as exc:
            undecided.append(
                {"role": role, "field": heading, "kind": "ambiguous", "lines": None, "why": str(exc)}
            )
            continue
        except gbf.FieldNotFoundError:
            absent.append(role)
            value = ""
        values[role] = "" if value == body.NO_RESPONSE else value
    return {"values": values, "absent": absent, "undecided": undecided}
