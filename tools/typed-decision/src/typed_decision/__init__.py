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

"""Provider-agnostic typed decision tool contract (Choice, Score, Noul)."""

from __future__ import annotations

from typing import Any

from typed_decision.exceptions import TypedDecisionUnavailable
from typed_decision.interface import DecisionProvider
from typed_decision.privacy import enforce_privacy_gate
from typed_decision.providers.jev import JevProvider
from typed_decision.registry import get_provider, register_provider

__all__ = [
    "DecisionProvider",
    "JevProvider",
    "TypedDecisionClient",
    "TypedDecisionUnavailable",
    "choice",
    "enforce_privacy_gate",
    "get_provider",
    "noul",
    "register_provider",
    "score",
]


def choice(
    prompt: str,
    options: list[str],
    *,
    provider: DecisionProvider | None = None,
) -> dict[str, Any]:
    """Select one discrete option label from candidates based on prompt.

    Returns:
        {"label": str, "confidence": float}
    """
    p = provider or get_provider()
    return p.choice(prompt, options)


def score(
    prompt: str,
    scale: tuple[float, float] | list[float] | int | float,
    *,
    provider: DecisionProvider | None = None,
) -> dict[str, Any]:
    """Score prompt along the specified scale.

    Returns:
        {"value": float | int, "confidence": float}
    """
    p = provider or get_provider()
    return p.score(prompt, scale)


def noul(
    prompt: str,
    *,
    provider: DecisionProvider | None = None,
) -> dict[str, Any]:
    """Evaluate null/binary decision probability for prompt.

    Returns:
        {"probability": float}
    """
    p = provider or get_provider()
    return p.noul(prompt)


class TypedDecisionClient:
    """Client wrapper for convenient object-oriented typed decision calls."""

    def __init__(self, provider: DecisionProvider | None = None, **kwargs: Any) -> None:
        self._provider = provider or get_provider(**kwargs)

    @property
    def provider(self) -> DecisionProvider:
        return self._provider

    def choice(self, prompt: str, options: list[str]) -> dict[str, Any]:
        return self._provider.choice(prompt, options)

    def score(
        self,
        prompt: str,
        scale: tuple[float, float] | list[float] | int | float,
    ) -> dict[str, Any]:
        return self._provider.score(prompt, scale)

    def noul(self, prompt: str) -> dict[str, Any]:
        return self._provider.noul(prompt)
