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

"""Read-only topic fetch, normalised to the mail-archive ``thread_data`` shape."""

from __future__ import annotations

import re
from typing import Any

from magpie_discourse.client import DiscourseConfig, DiscourseError, get_json, origin, parse_url

#: Posts returned per ``/t/{id}/posts.json`` request; Discourse's own chunk size.
POSTS_CHUNK_SIZE = 20
#: Default ceiling on posts read for one topic; a longer topic is marked truncated.
DEFAULT_MAX_POSTS = 500

_TOPIC_PATH = re.compile(r"^/t/(?:[^/]+/)?(?P<id>[0-9]+)(?:/[0-9]+)?(?:\.json)?/?$")
_SHORT_TOPIC_PATH = re.compile(r"^/t/(?P<id>[0-9]+)(?:/[0-9]+)?(?:\.json)?/?$")


def parse_topic_ref(ref: str, config: DiscourseConfig) -> int:
    """Return the topic id from a numeric id or a topic URL on the configured forum."""
    value = ref.strip()
    if re.fullmatch(r"[0-9]+", value):
        topic_id = int(value)
        if topic_id > 0:
            return topic_id
        raise DiscourseError("Topic id must be a positive integer")
    if value.isdigit():
        raise DiscourseError("Topic id must use ASCII digits")

    parsed = parse_url(value)
    base = parse_url(config.base_url)
    if origin(parsed) != origin(base) or parsed.username is not None:
        raise DiscourseError(f"Topic URL is not on the configured forum {config.base_url}: {ref}")
    path = parsed.path
    if base.path and not path.startswith(f"{base.path}/"):
        raise DiscourseError(f"Topic URL is not under the configured forum path {base.path}: {ref}")
    topic_path = path[len(base.path) :]
    # Match the numeric topic/post route before the slug/topic route, like Discourse.
    match = _SHORT_TOPIC_PATH.match(topic_path) or _TOPIC_PATH.match(topic_path)
    if not match or int(match.group("id")) < 1:
        raise DiscourseError(f"Not a Discourse topic URL: {ref}")
    return int(match.group("id"))


def fetch_topic(config: DiscourseConfig, topic_id: int, max_posts: int = DEFAULT_MAX_POSTS) -> dict[str, Any]:
    """Fetch a topic and its posts, up to ``max_posts``, as one ``thread_data`` record."""
    if not _positive_int(topic_id):
        raise DiscourseError("Topic id must be a positive integer")
    if not _positive_int(max_posts):
        raise DiscourseError("max_posts must be at least 1")

    raw = get_json(config, f"/t/{topic_id}.json")
    if not _positive_int(raw.get("id")) or raw["id"] != topic_id or not isinstance(raw.get("title"), str):
        raise DiscourseError("Discourse returned an invalid topic id or title")
    initial_posts = _read_posts(raw)
    post_ids = raw["post_stream"].get("stream")
    if post_ids is None and raw["post_stream"].get("isMegaTopic") is True:
        raise DiscourseError("Discourse mega topics without a post ID stream are not supported")
    if not isinstance(post_ids, list) or any(not _positive_int(post_id) for post_id in post_ids):
        raise DiscourseError("Discourse returned an invalid or missing topic post stream")
    if len(set(post_ids)) != len(post_ids):
        raise DiscourseError("Discourse returned duplicate post ids in the topic stream")
    if not post_ids and (initial_posts or raw.get("posts_count")):
        raise DiscourseError("Discourse returned an empty stream for a non-empty topic")
    if raw.get("tags") is not None and not isinstance(raw["tags"], list):
        raise DiscourseError("Discourse returned invalid topic tags")
    posts = {post["id"]: post for post in initial_posts}

    wanted = post_ids[:max_posts]
    missing = [post_id for post_id in wanted if post_id not in posts]
    for start in range(0, len(missing), POSTS_CHUNK_SIZE):
        chunk = missing[start : start + POSTS_CHUNK_SIZE]
        extra = get_json(config, f"/t/{topic_id}/posts.json", {"post_ids[]": chunk})
        for post in _read_posts(extra):
            posts[post["id"]] = post
        absent = [post_id for post_id in chunk if post_id not in posts]
        if absent:
            raise DiscourseError(
                f"Discourse did not return {len(absent)} requested post(s) for topic {topic_id}"
            )
    ordered = [posts[post_id] for post_id in wanted]
    return normalize_topic(raw, ordered, config, truncated=len(post_ids) > len(wanted))


def normalize_topic(
    raw: dict[str, Any], posts: list[dict[str, Any]], config: DiscourseConfig, *, truncated: bool
) -> dict[str, Any]:
    """Map validated posts onto the mail-archive ``thread_data`` field shape."""
    topic_id = raw.get("id")
    slug = raw.get("slug") or "-"
    url = f"{config.base_url}/t/{slug}/{topic_id}"
    id_by_number = {post.get("post_number"): post.get("id") for post in posts}

    messages = []
    handles: list[str] = []
    seen_handles: set[str] = set()
    for post in posts:
        username = post.get("username")
        handle = f"@{username}" if username else None
        if handle and handle not in seen_handles:
            seen_handles.add(handle)
            handles.append(handle)
        reply_to = post.get("reply_to_post_number")
        messages.append(
            {
                "message_id": str(post.get("id")),
                "post_number": post.get("post_number"),
                "from": handle,
                "date": post.get("created_at"),
                "updated_at": post.get("updated_at"),
                "body": post["cooked"],
                "body_hidden": post.get("cooked_hidden") is True,
                "body_format": "html",
                "in_reply_to": str(id_by_number[reply_to]) if id_by_number.get(reply_to) else None,
                "url": f"{url}/{post.get('post_number')}",
                "post_type": post.get("post_type"),
                "hidden": bool(post.get("hidden")),
                "deleted": bool(post.get("deleted_at") or post.get("user_deleted")),
            }
        )

    return {
        "thread_id": str(topic_id),
        "list": config.base_url,
        "subject": raw.get("title"),
        "url": url,
        "category_id": raw.get("category_id"),
        "tags": [_tag_name(tag) for tag in raw.get("tags") or []],
        "created_at": raw.get("created_at"),
        "last_posted_at": raw.get("last_posted_at"),
        "posts_count": raw.get("posts_count"),
        "closed": bool(raw.get("closed")),
        "archived": bool(raw.get("archived")),
        "messages": messages,
        "participant_handles": handles,
        "truncated": truncated,
    }


def _tag_name(tag: Any) -> str:
    """Return a tag's name; newer Discourse sends tag objects, older ones plain strings."""
    if isinstance(tag, dict):
        return str(tag.get("name") or tag.get("slug") or "")
    return str(tag)


def _positive_int(value: Any) -> bool:
    """True for positive integer identifiers and limits, excluding JSON booleans."""
    return type(value) is int and value > 0


def _read_posts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the required post collection without treating malformed data as an empty topic."""
    stream = payload.get("post_stream")
    if not isinstance(stream, dict) or not isinstance(stream.get("posts"), list):
        raise DiscourseError("Discourse returned an invalid or missing post collection")
    posts: list[dict[str, Any]] = []
    for post in stream["posts"]:
        if (
            not isinstance(post, dict)
            or not _positive_int(post.get("id"))
            or not _positive_int(post.get("post_number"))
            or not isinstance(post.get("created_at"), str)
            or not isinstance(post.get("username"), str | type(None))
            or (
                post.get("reply_to_post_number") is not None
                and not _positive_int(post["reply_to_post_number"])
            )
        ):
            raise DiscourseError("Discourse returned an invalid post record")
        if not isinstance(post.get("cooked"), str):
            raise DiscourseError(f"Discourse returned a missing or invalid cooked body for post {post['id']}")
        if not isinstance(post.get("cooked_hidden", False), bool):
            raise DiscourseError(f"Discourse returned an invalid cooked_hidden flag for post {post['id']}")
        posts.append(post)
    return posts
