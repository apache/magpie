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
"""``egress-gateway`` console script — start the allowlisting forward proxy.

Launches proxy.py bound to loopback with the
:class:`egress_gateway.allowlist.EgressAllowlistPlugin` loaded, so every
upstream host is checked against the allowlist before a socket is opened.

Operational notes (see README.md for the full story):

* **Binding a listen socket is blocked inside the framework's sandbox.** Run
  the gateway from a context that is *not* sandboxed (it is the egress-control
  point, so it legitimately needs unrestricted outbound).
* **proxy.py keeps runtime state under ``$HOME/.proxy``.** If HOME is not
  writable in your environment, point it at a writable dir for this process
  (``HOME=/tmp/egress-home egress-gateway``).
* Extra allowed hosts: ``EGRESS_ALLOW_EXTRA=host1,.suffix2 egress-gateway``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8899
_PLUGIN = "egress_gateway.allowlist.EgressAllowlistPlugin"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="egress-gateway",
        description="Allowlisting HTTP(S) forward proxy (egress-control chokepoint).",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="bind port (default: 8899)")
    parser.add_argument("--log-level", default="INFO", help="proxy.py log level (default: INFO)")
    args, passthrough = parser.parse_known_args(argv)

    # Imported lazily so `--help` works even if proxy.py is somehow absent.
    import proxy

    with proxy.Proxy(
        input_args=[
            "--hostname",
            args.host,
            "--port",
            str(args.port),
            "--plugins",
            _PLUGIN,
            "--log-level",
            args.log_level,
            *passthrough,
        ]
    ):
        proxy.sleep_loop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
