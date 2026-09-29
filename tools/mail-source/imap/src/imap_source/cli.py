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
"""CLI plumbing shared by the ``imap-source-*`` console scripts.

Exit codes follow the mail-source contract's *decline, don't fake* rule:

- ``0`` — the operation ran and printed JSON on stdout;
- ``2`` — configuration error (missing/invalid environment);
- ``3`` — capability declined (the op is not supported by this account's
  folders — e.g. a read-only shared role mailbox declining the drafts ops);
- ``4`` — server-side operation failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

from imap_source.config import ConfigError, ImapConfig
from imap_source.mailbox import ImapOperationError, Mailbox

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_DECLINED = 3
EXIT_SERVER = 4


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def load_config() -> ImapConfig:
    """Read the adopter's environment, mapping a missing setup to exit code 2."""
    try:
        return ImapConfig.from_env()
    except ConfigError as exc:
        eprint(f"imap-source: configuration error: {exc}")
        raise SystemExit(EXIT_CONFIG) from None


def add_since_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--since-days", type=int, default=90, help="search window in days (default: 90)")


class CapabilityDeclined(RuntimeError):
    """This account cannot serve the operation — decline instead of faking it."""


def print_json(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")


def with_mailbox(operation: Callable[[Mailbox, ImapConfig], object]) -> int:
    """Connect, then run the operation — server failures during connect map to exit 4."""
    config = load_config()
    try:
        mailbox = Mailbox.connect(config)
    except (ImapOperationError, ConnectionError, TimeoutError, OSError) as exc:
        eprint(f"imap-source: server error: {exc}")
        return EXIT_SERVER
    return run_operation(lambda: operation(mailbox, config))


def run_operation(operation: Callable[[], object]) -> int:
    """Execute an operation callable and translate failures into exit codes."""
    try:
        payload = operation()
    except ConfigError as exc:
        print(f"imap-source: configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except CapabilityDeclined as exc:
        print(f"imap-source: capability declined: {exc}", file=sys.stderr)
        return EXIT_DECLINED
    except ImapOperationError as exc:
        print(f"imap-source: server error: {exc}", file=sys.stderr)
        return EXIT_SERVER
    except (ConnectionError, TimeoutError, OSError) as exc:
        print(f"imap-source: server error: {exc}", file=sys.stderr)
        return EXIT_SERVER
    print_json(payload)
    return EXIT_OK
