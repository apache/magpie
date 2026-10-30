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

"""Run `gh` with retries on transient failures; shared by the fetch scripts."""

import re
import subprocess
import sys
import time

# `gh` reports a server-side hiccup as a non-zero exit with the status in stderr.
# A single transient `HTTP 502` on the first call used to abort the entire
# dashboard run, so retry the failures that are worth retrying and fail fast on
# everything else (auth errors, a bad repo slug, an unknown flag).
_TRANSIENT_FAILURE = re.compile(
    r"HTTP\s+5\d\d"
    r"|Bad Gateway"
    r"|Service Unavailable"
    r"|Gateway Time-?out"
    r"|Internal Server Error"
    r"|connection reset"
    r"|timed out",
    re.IGNORECASE,
)

ATTEMPTS = 3
BASE_DELAY_SECONDS = 2.0


def is_transient_failure(stderr: str) -> bool:
    """True when a failed `gh` call looks like a retryable server-side error."""
    return bool(_TRANSIENT_FAILURE.search(stderr or ""))


def run_gh(
    args: list[str],
    *,
    attempts: int = ATTEMPTS,
    base_delay: float = BASE_DELAY_SECONDS,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Run `gh`, retrying transient failures with exponential backoff.

    Raises `SystemExit` with the last stderr once the attempts are exhausted, or
    immediately for a failure that retrying cannot fix.
    """
    for attempt in range(1, attempts + 1):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            # A call that hangs past the timeout is a server-side stall, so it is
            # retried like a 504 rather than aborting the run.
            stderr = f"gh timed out after {timeout}s"
        else:
            if r.returncode == 0:
                return r
            stderr = r.stderr
            if not is_transient_failure(stderr):
                raise SystemExit(f"gh failed: {stderr}")
        if attempt == attempts:
            raise SystemExit(f"gh failed: {stderr}")
        delay = base_delay * 2 ** (attempt - 1)
        print(
            f"gh failed (attempt {attempt}/{attempts}), retrying in {delay:g}s: "
            f"{(stderr or '').strip()[:200]}",
            file=sys.stderr,
        )
        time.sleep(delay)
    raise AssertionError("unreachable: run_gh returns or raises on every attempt")
