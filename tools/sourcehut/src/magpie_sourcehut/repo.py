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

"""git.sr.ht and hg.sr.ht repository integration."""

from __future__ import annotations

from typing import Any

from magpie_sourcehut.client import query_graphql


def _normalize_owner(owner: str) -> str:
    """Ensure the owner username starts with '~'."""
    if not owner.startswith("~"):
        return f"~{owner}"
    return owner


def get_repo(service: str, owner: str, name: str) -> dict[str, Any]:
    """Retrieve repository details from git.sr.ht or hg.sr.ht.

    Args:
        service: 'git' or 'hg'.
        owner: Repository owner.
        name: Repository name.
    """
    if service not in ("git", "hg"):
        raise ValueError("Service must be 'git' or 'hg'")

    owner = _normalize_owner(owner)
    q = """
    query GetRepository($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        name
        description
        visibility
        updated
      }
    }
    """
    res = query_graphql(service, q, {"owner": owner, "name": name})
    return res.get("repository") or {}
