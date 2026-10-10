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
"""Which `@`-mentions a rendered body may keep live.

Every renderer in this package backtick-quotes handles so a posted body
notifies nobody but the PR author. A project can name handles that may stay
live everywhere — `mention_allowlist` in `<project-config>/pr-management-config.md`
— and one call can add more with `--allow-mention <login>`. The agent-guard
`mention` guard honours the same key, read from the committed copy only, so
the two never disagree about a reviewed allowlist.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable

from .config import Config


def normalize(handle: str) -> str:
    """`@Login` / `login` / `@org/team` → lower-case, without the `@`."""
    return handle.strip().lstrip("@").lower()


def allowed(cfg: Config, extra: Iterable[str] = ()) -> frozenset[str]:
    """The configured allowlist plus any per-call additions."""
    return frozenset(h for h in (normalize(x) for x in (*cfg.mention_allowlist, *extra)) if h)


def add_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-mention",
        action="append",
        default=[],
        metavar="LOGIN",
        help="keep this @-mention live for this call (repeatable); the guard also needs MAGPIE_ALLOW_MENTIONS=1 "
        "on the posting command unless the handle is in the mention_allowlist on the target repository's default branch",
    )


def apply_flag(cfg: Config, args: argparse.Namespace) -> Config:
    """Fold `--allow-mention` values into the loaded config."""
    cfg.mention_allowlist = [*cfg.mention_allowlist, *getattr(args, "allow_mention", [])]
    return cfg
