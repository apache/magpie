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

"""Abstract provider interface for typed decisions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DecisionProvider(ABC):
    """Abstract interface that any typed-decision provider backend implements."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier (e.g. 'jev')."""
        ...

    @abstractmethod
    def choice(self, prompt: str, options: list[str]) -> dict[str, Any]:
        """Select a single discrete label from given options based on prompt.

        Args:
            prompt: Question or context for decision.
            options: Non-empty list of candidate labels.

        Returns:
            dict containing:
                "label": str (selected option),
                "confidence": float (between 0.0 and 1.0).

        Raises:
            TypedDecisionUnavailable: On provider/network failure, timeout, or missing config.
        """
        ...

    @abstractmethod
    def score(
        self,
        prompt: str,
        scale: tuple[float, float] | list[float] | int | float,
    ) -> dict[str, Any]:
        """Evaluate a score for the prompt along the specified scale.

        Args:
            prompt: Text to be scored.
            scale: Range or upper bound (e.g. (1, 5), (0, 10), or numeric max).

        Returns:
            dict containing:
                "value": float | int (assigned score),
                "confidence": float (between 0.0 and 1.0).

        Raises:
            TypedDecisionUnavailable: On provider/network failure, timeout, or missing config.
        """
        ...

    @abstractmethod
    def noul(self, prompt: str) -> dict[str, Any]:
        """Compute the null / binary hypothesis decision probability.

        Args:
            prompt: Proposition or prompt to evaluate.

        Returns:
            dict containing:
                "probability": float (between 0.0 and 1.0).

        Raises:
            TypedDecisionUnavailable: On provider/network failure, timeout, or missing config.
        """
        ...
