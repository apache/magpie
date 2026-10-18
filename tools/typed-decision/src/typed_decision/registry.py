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

"""Provider registry and configuration resolution for typed decisions."""

from __future__ import annotations

import os
from typing import Any

from typed_decision.exceptions import TypedDecisionUnavailable
from typed_decision.interface import DecisionProvider
from typed_decision.providers.jev import JevProvider, _resolve_api_key
from typed_decision.providers.local import LocalProvider

DEFAULT_PROVIDER_ENV = "MAGPIE_TYPED_DECISION_PROVIDER"

_REGISTRY: dict[str, type[DecisionProvider]] = {
    "jev": JevProvider,
    "local": LocalProvider,
}


def register_provider(name: str, provider_cls: type[DecisionProvider]) -> None:
    """Register a provider class in the registry."""
    _REGISTRY[name.strip().lower()] = provider_cls


def _is_jev_configured() -> bool:
    """Check if Jev credentials are configured in environment or home directory."""
    return _resolve_api_key() is not None


def get_provider(name: str | None = None, **kwargs: Any) -> DecisionProvider:
    """Resolve and instantiate a typed decision provider.

    Resolution order:
    1. Explicit `name` argument if provided.
    2. Environment variable `$MAGPIE_TYPED_DECISION_PROVIDER` if set.
    3. If neither is set, defaults to 'jev' IF configured (i.e. credentials exist).
    4. If not configured, raises TypedDecisionUnavailable.

    Raises:
        TypedDecisionUnavailable: If the provider is unknown, or if no provider is configured.
    """
    selected_name = name or os.environ.get(DEFAULT_PROVIDER_ENV)

    if selected_name:
        normalized = selected_name.strip().lower()
        provider_cls = _REGISTRY.get(normalized)
        if provider_cls is None:
            raise TypedDecisionUnavailable(
                f"Unknown typed decision provider '{selected_name}'. "
                f"Available providers: {', '.join(sorted(_REGISTRY.keys()))}"
            )
        return provider_cls(**kwargs)

    # Unset: default to 'jev' if configured, else unavailable
    if _is_jev_configured():
        return JevProvider(**kwargs)

    raise TypedDecisionUnavailable(
        "No typed decision provider configured. Set MAGPIE_TYPED_DECISION_PROVIDER "
        "or provide TYPESAFE_API_KEY credentials for the default 'jev' provider."
    )
