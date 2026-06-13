#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
"""Mock judge grader: returns holds=true for every ``Property: <key>`` in stdin.

Stand-in for ``claude -p --model haiku`` in batch_judge_assertions tests.
"""

from __future__ import annotations

import json
import re
import sys


def main() -> None:
    keys = re.findall(r"^Property: (\S+)", sys.stdin.read(), flags=re.MULTILINE)
    print(json.dumps({k: {"holds": True, "reason": "ok"} for k in keys}))


if __name__ == "__main__":
    main()
