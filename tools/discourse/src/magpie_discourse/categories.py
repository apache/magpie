# SPDX-License-Identifier: Apache-2.0
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

"""Resolve category references without requesting user-supplied category URLs."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.request import Request

from magpie_discourse.client import DiscourseConfig, DiscourseError, SameOriginRedirectHandler, get_json


def _slug(value: str) -> str:
    """Decode one slug component, refusing ambiguous or nested escapes."""
    if re.search(r"%(?![0-9a-fA-F]{2})|%(?:2f|5c)", value, re.IGNORECASE):
        raise DiscourseError("Invalid category slug encoding")
    try:
        decoded = unquote(value, errors="strict")
    except UnicodeDecodeError as exc:
        raise DiscourseError("Invalid category slug encoding") from exc
    if (
        not decoded
        or decoded in (".", "..")
        or any(char in decoded for char in "/\\%?#")
        or any(ord(char) < 32 or ord(char) == 127 for char in decoded)
    ):
        raise DiscourseError("Invalid category slug or path")
    return decoded


def _category(raw: Any) -> dict[str, Any]:
    """Validate the metadata required for a category selection."""
    if (
        not isinstance(raw, dict)
        or type(raw.get("id")) is not int
        or raw["id"] < 1
        or not isinstance(raw.get("slug"), str)
        or not isinstance(raw.get("name"), str)
    ):
        raise DiscourseError("Discourse returned invalid category metadata")
    return {key: raw[key] for key in ("id", "slug", "name")}


def resolve_category(config: DiscourseConfig, ref: str) -> dict[str, Any]:
    """Resolve an ID, an ID-bearing reference or a top-level catalog slug."""
    value = ref.strip()
    if "/" in value:
        if value.startswith("//"):
            raise DiscourseError("Category references starting with // are not supported")
        base = urlsplit(config.base_url)
        if value.startswith("/"):
            prefix = (
                f"{base.scheme}://{base.netloc}" if value.startswith(f"{base.path}/") else config.base_url
            )
            target = prefix + value
        else:
            target = value if "://" in value else f"{config.base_url}/c/{value}"
        try:
            SameOriginRedirectHandler(config.base_url).check_request(Request(target, method="GET"))
        except ValueError as exc:
            raise DiscourseError("Invalid category URL") from exc
        path = urlsplit(target).path[len(base.path) :]
        match = re.fullmatch(r"/c/(?:[^/]+/)*([0-9]+)/?", path)
        if not match:
            raise DiscourseError(
                "Unsupported category reference; use /c/.../ID or a numeric id. "
                "List-view suffixes and .json are not supported."
            )
        value = match[1]
    if value.startswith(("+", "-")) and value[1:].isdigit():
        raise DiscourseError("Category id must be a positive integer using ASCII digits")
    if value.isdigit():
        if not re.fullmatch(r"[0-9]+", value):
            raise DiscourseError("Category id must use ASCII digits")
        try:
            category_id = int(value)
        except ValueError as exc:
            raise DiscourseError("Invalid category id") from exc
        if category_id < 1:
            raise DiscourseError("Category id must be a positive integer")
        category = _category(get_json(config, f"/c/{category_id}/show.json").get("category"))
        if category["id"] != category_id:
            raise DiscourseError("Discourse returned a different category id")
        return category

    wanted = _slug(value)
    payload = get_json(config, "/categories.json")
    envelope = payload.get("category_list")
    if not isinstance(envelope, dict) or not isinstance(envelope.get("categories"), list):
        raise DiscourseError("Discourse returned an invalid category collection")
    matches = []
    for raw in envelope["categories"]:
        category = _category(raw)
        parent_id = raw.get("parent_category_id")
        if parent_id is not None:
            if type(parent_id) is not int or parent_id < 1:
                raise DiscourseError("Discourse returned an invalid parent category id")
            continue
        try:
            slug = _slug(category["slug"])
        except DiscourseError:
            continue
        if slug == wanted:
            matches.append(category)
    if len(matches) > 1:
        raise DiscourseError("Category slug is ambiguous; use a numeric id")
    if not matches:
        raise DiscourseError("Cannot resolve top-level category from the returned catalog; use a numeric id")
    return matches[0]
