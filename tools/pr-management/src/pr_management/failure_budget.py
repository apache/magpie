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

"""Per-item failure budget for a batch sweep's read and classify phase.

docs/batch-failure-budget.md is the contract. In short: one item whose state
cannot be read or classified is recorded as ``failed`` with its reason and the
sweep carries on; only when more items fail than the budget allows does the
sweep stop, and then every item it did not reach is reported as unfinished.
The write phase is not budgeted: a failed post still stops at once, because a
retried write can duplicate a visible action.

The budget is ``item_failure_budget`` in the project's config, one of:

* ``<n>`` — an absolute count of tolerated item failures;
* ``<p>%`` — a share of the pool, rounded down;
* ``max(<n>, <p>%)`` — whichever is larger.

The default is ``max(3, 10%)``. A malformed value is an error, never a
silent fallback to the default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_SPEC = "max(3, 10%)"

_COUNT = re.compile(r"^(\d+)$")
_SHARE = re.compile(r"^(\d+(?:\.\d+)?)%$")
_MAX = re.compile(r"^max\(\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)%\s*\)$")


class BudgetSpecError(ValueError):
    """``item_failure_budget`` is not one of the accepted shapes."""


def limit(spec: str | None, pool_size: int) -> int:
    """How many item failures a pool of ``pool_size`` tolerates under ``spec``."""
    text = (spec or DEFAULT_SPEC).strip().lower()
    if pool_size < 0:
        raise ValueError("pool_size must not be negative")
    if m := _COUNT.match(text):
        return int(m.group(1))
    if m := _SHARE.match(text):
        return _share(float(m.group(1)), pool_size)
    if m := _MAX.match(text):
        return max(int(m.group(1)), _share(float(m.group(2)), pool_size))
    raise BudgetSpecError(
        f"item_failure_budget {spec!r} is not <n>, <p>% or max(<n>, <p>%) (default {DEFAULT_SPEC})"
    )


def _share(percent: float, pool_size: int) -> int:
    if percent > 100:
        raise BudgetSpecError(f"item_failure_budget share {percent}% is over 100%")
    return int(pool_size * percent / 100)


@dataclass
class Budget:
    """Failure accounting for one sweep."""

    limit: int
    failed: list[dict[str, object]] = field(default_factory=list)

    @property
    def exhausted(self) -> bool:
        """True once more items have failed than the budget tolerates."""
        return len(self.failed) > self.limit

    def record(self, item: object, reason: str) -> None:
        self.failed.append({"item": item, "reason": reason})

    def as_dict(self) -> dict[str, object]:
        return {
            "limit": self.limit,
            "used": len(self.failed),
            "exhausted": self.exhausted,
            "failed": list(self.failed),
        }


def rerun_selector(numbers: list[int]) -> str | None:
    """The ``NN,MM,...`` selector that reruns exactly ``numbers``, or None when empty."""
    return ",".join(str(n) for n in sorted(set(numbers))) or None
