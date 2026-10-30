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

"""Read category activity with evidence-based truncation and no partial success."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from magpie_discourse.categories import resolve_category
from magpie_discourse.client import DiscourseConfig, DiscourseError, get_json

DEFAULT_LIMIT = 100
_DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_TIMESTAMP = re.compile(_DATE + r"T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})")


def _timestamp(value: Any, field: str, *, allow_date: bool = False) -> datetime:
    """Parse explicit ISO times without silently discarding sub-microsecond precision."""
    message = f"Invalid {field}: use an ISO-8601 timestamp with a timezone and at most six fractional digits"
    if not isinstance(value, str):
        raise DiscourseError(message)
    try:
        if allow_date and re.fullmatch(_DATE, value):
            return datetime.fromisoformat(value).replace(tzinfo=UTC)
        if not _TIMESTAMP.fullmatch(value):
            raise DiscourseError(message)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise DiscourseError(message) from exc


def _summary(raw: Any, config: DiscourseConfig) -> tuple[dict[str, Any], datetime]:
    """Validate one summary independently of the topic-view post schema."""
    if (
        not isinstance(raw, dict)
        or type(raw.get("id")) is not int
        or raw["id"] < 1
        or not isinstance(raw.get("title"), str)
        or type(raw.get("posts_count")) is not int
        or raw["posts_count"] < 0
    ):
        raise DiscourseError("Discourse returned an invalid topic summary")
    _timestamp(raw.get("created_at"), "topic created_at")
    bumped = _timestamp(raw.get("bumped_at"), "topic bumped_at")
    last_posted = raw.get("last_posted_at")
    if last_posted is not None:
        _timestamp(last_posted, "topic last_posted_at")
    for field in ("pinned", "closed", "archived"):
        if not isinstance(raw.get(field, False), bool):
            raise DiscourseError(f"Discourse returned an invalid topic {field} flag")
    tags = raw.get("tags")
    if tags is None:
        tags = []
    if not isinstance(tags, list):
        raise DiscourseError("Discourse returned invalid topic tags")
    names = []
    for tag in tags:
        name = (tag.get("name") or tag.get("slug")) if isinstance(tag, dict) else tag
        if not isinstance(name, str):
            raise DiscourseError("Discourse returned an invalid topic tag")
        names.append(name)
    return {
        "thread_id": str(raw["id"]),
        "subject": raw["title"],
        "first_message_date": raw["created_at"],
        "last_message_date": last_posted,
        "bumped_at": raw["bumped_at"],
        "message_count": raw["posts_count"],
        "permalink": f"{config.base_url}/t/{raw['id']}",
        "tags": names,
        "pinned": raw.get("pinned", False),
        "closed": raw.get("closed", False),
        "archived": raw.get("archived", False),
    }, bumped


def list_topics(
    config: DiscourseConfig, category: str, *, since: str | None = None, limit: int = DEFAULT_LIMIT
) -> dict[str, Any]:
    """Return at most ``limit`` unique matches, looking ahead for proof of truncation."""
    if type(limit) is not int or limit < 1:
        raise DiscourseError("limit must be at least 1")
    lower_bound = _timestamp(since, "since", allow_date=True) if since is not None else None
    selected = resolve_category(config, category)
    threads: list[dict[str, Any]] = []
    matched_ids: set[str] = set()
    seen_pages: set[tuple[str, ...]] = set()
    page = 0
    while True:
        payload = get_json(
            config,
            "/latest.json",
            {
                "category": selected["id"],
                "order": "activity",
                "ascending": "false",
                "no_subcategories": "false",
                "page": page,
            },
        )
        envelope = payload.get("topic_list")
        if not isinstance(envelope, dict) or not isinstance(envelope.get("topics"), list):
            raise DiscourseError("Discourse returned an invalid topic summary collection")
        # Validate the entire response page, including records outside the output cap.
        summaries = [_summary(raw, config) for raw in envelope["topics"]]
        continuation = envelope.get("more_topics_url")
        if continuation is not None and not isinstance(continuation, str):
            raise DiscourseError("Discourse returned an invalid pagination signal")
        more = bool(continuation)
        fingerprint = tuple(summary["thread_id"] for summary, _ in summaries)
        if more and (not summaries or fingerprint in seen_pages):
            raise DiscourseError(
                "Cannot reliably continue Discourse pagination: empty or repeated complete page"
            )
        seen_pages.add(fingerprint)
        for raw, (summary, bumped) in zip(envelope["topics"], summaries, strict=True):
            if lower_bound is not None and bumped < lower_bound:
                # Native activity order bounds the remaining non-pinned topics.
                # An omitted flag's output default is not evidence of pin status.
                if raw.get("pinned") is False:
                    return _result(selected, lower_bound, threads, truncated=False)
                continue
            if summary["thread_id"] in matched_ids:
                continue
            matched_ids.add(summary["thread_id"])
            threads.append(summary)
            if len(threads) > limit:
                return _result(selected, lower_bound, threads[:limit], truncated=True)
        if not more:
            return _result(selected, lower_bound, threads, truncated=False)
        page += 1


def _result(
    category: dict[str, Any], since: datetime | None, threads: list[dict[str, Any]], *, truncated: bool
) -> dict[str, Any]:
    """Build the successful result only after all required reads have succeeded."""
    return {
        "category": category,
        "since": since.isoformat().replace("+00:00", "Z") if since is not None else None,
        "threads": threads,
        "truncated": truncated,
    }
