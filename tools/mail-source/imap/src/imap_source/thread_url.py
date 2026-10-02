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
"""``thread_url(thread_id)`` — human-clickable archive deep-link (best-effort)."""

from __future__ import annotations

import argparse

from imap_source.archive_url import thread_url as build_thread_url
from imap_source.cli import eprint, load_config, run_operation
from imap_source.config import ImapConfig


def resolve_thread_url(config: ImapConfig, thread_id: str) -> dict[str, str]:
    url = build_thread_url(config, thread_id)
    return {
        "thread_id": thread_id,
        "url": url,
        "kind": "archive-template" if config.archive_template else "imap-fallback",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="imap-source-thread-url",
        description="Build a human-clickable URL for a thread (archive template or imap:// fallback).",
    )
    parser.add_argument("thread_id", help="root RFC-5322 Message-ID of the thread")
    args = parser.parse_args(argv)

    config = load_config()
    if config.archive_template:
        eprint("using the configured archive template")
    else:
        eprint("no IMAP_SOURCE_ARCHIVE_TEMPLATE configured — falling back to an imap:// URL")
    return run_operation(lambda: resolve_thread_url(config, args.thread_id))


if __name__ == "__main__":
    raise SystemExit(main())
