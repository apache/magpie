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

"""Find forum topics and the posts that matched a native Discourse query."""

from __future__ import annotations

from typing import Any

from magpie_discourse.client import DiscourseConfig, DiscourseError, get_json

DEFAULT_LIMIT = 100
# Discourse's full-page search endpoint rejects page 11.
_LAST_PAGE = 10


def _has_positive_ids(row: Any, *fields: str) -> bool:
    return isinstance(row, dict) and all(type(row.get(key)) is int and row[key] > 0 for key in fields)


def _read_page(payload: dict[str, Any], page: int) -> tuple[list[dict[str, Any]], dict[int, str], bool]:
    group = payload.get("grouped_search_result")
    if group is None and "grouped_search_result" in payload:
        if page == 1:
            raise DiscourseError(
                "No searchable terms remain in this query. Try adding a keyword or using a longer one."
            )
        raise DiscourseError(f"Discourse returned a null search result group on page {page}.")
    if not isinstance(group, dict):
        raise DiscourseError("Discourse returned invalid grouped search results")
    error = group.get("error")
    if error is not None and not isinstance(error, str):
        raise DiscourseError("Discourse returned an invalid search error")
    if error:
        raise DiscourseError(f"Discourse search failed: {error}")
    more = group.get("more_full_page_results")
    if "more_full_page_results" not in group or (more is not None and not isinstance(more, bool)):
        raise DiscourseError("Discourse returned an invalid search pagination signal")

    posts = payload.get("posts")
    # An empty result can omit the sideloaded topics collection.
    topics = payload.get("topics", [])
    if not isinstance(posts, list) or not isinstance(topics, list):
        raise DiscourseError("Discourse returned invalid search posts or topics")
    titles: dict[int, str] = {}
    for topic in topics:
        if not _has_positive_ids(topic, "id") or not isinstance(topic.get("title"), str):
            raise DiscourseError("Discourse returned an invalid search topic")
        titles[topic["id"]] = topic["title"]
    for post in posts:
        if (
            not _has_positive_ids(post, "id", "topic_id", "post_number")
            or not isinstance(post.get("username"), str | None)
            or not isinstance(post.get("created_at"), str)
            or not isinstance(post.get("blurb"), str)
        ):
            raise DiscourseError("Discourse returned an invalid search post")
        if post["topic_id"] not in titles:
            raise DiscourseError(f"Discourse omitted topic {post['topic_id']} for search post {post['id']}")
    return posts, titles, more is True


def search_topics(config: DiscourseConfig, query: str, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return the first distinct topics in server order, with matches from the pages read."""
    if not query.strip():
        raise DiscourseError("search query must not be blank")
    if type(limit) is not int or limit < 1:
        raise DiscourseError("limit must be at least 1")

    threads: dict[int, dict[str, Any]] = {}
    seen_posts: set[int] = set()
    seen_pages: set[tuple[int, ...]] = set()
    truncated = False
    page = 1
    while True:
        payload = get_json(config, "/search.json", {"q": query, "page": page})
        posts, titles, more = _read_page(payload, page)
        fingerprint = tuple(post["id"] for post in posts)
        if more and (not posts or fingerprint in seen_pages):
            raise DiscourseError("Cannot continue Discourse search: empty or repeated complete page")
        seen_pages.add(fingerprint)
        for post in posts:
            if post["id"] in seen_posts:
                continue
            seen_posts.add(post["id"])
            topic_id = post["topic_id"]
            if topic_id not in threads:
                if len(threads) == limit:
                    truncated = True
                    continue
                threads[topic_id] = {
                    "thread_id": str(topic_id),
                    "subject": titles[topic_id],
                    "permalink": f"{config.base_url}/t/{topic_id}",
                    "matches": [],
                }
            thread = threads[topic_id]
            username = post.get("username")
            thread["matches"].append(
                {
                    "message_id": str(post["id"]),
                    "post_number": post["post_number"],
                    "from": f"@{username}" if username else None,
                    "date": post["created_at"],
                    "excerpt": post["blurb"],
                    "url": f"{thread['permalink']}/{post['post_number']}",
                }
            )
        if truncated or not more or page == _LAST_PAGE:
            break
        page += 1

    return {
        "query": query,
        "threads": list(threads.values()),
        "truncated": truncated,
        "server_limit_reached": page == _LAST_PAGE and more,
    }
