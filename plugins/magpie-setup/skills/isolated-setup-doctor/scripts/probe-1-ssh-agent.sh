#!/usr/bin/env bash
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

if [ -z "$SSH_AUTH_SOCK" ]; then
  echo "PROBE: ssh-agent → ⊘ (SSH_AUTH_SOCK not set in env)"
elif [ ! -S "$SSH_AUTH_SOCK" ]; then
  echo "PROBE: ssh-agent → ✗ (socket file at SSH_AUTH_SOCK not stat-able from inside sandbox)"
  echo "       SSH_AUTH_SOCK=$SSH_AUTH_SOCK"
else
  ssh-add -l > /tmp/ssh-add.out 2>&1; rc=$?
  case "$rc" in
    0) echo "PROBE: ssh-agent → ✓ ($(wc -l < /tmp/ssh-add.out | tr -d ' ') identities listed)" ;;
    1) echo "PROBE: ssh-agent → ✓ (agent reachable, no identities configured)" ;;
    2) echo "PROBE: ssh-agent → ✗ (agent unreachable: $(head -1 /tmp/ssh-add.out))" ;;
    *) echo "PROBE: ssh-agent → ⚠ (unexpected rc=$rc: $(head -1 /tmp/ssh-add.out))" ;;
  esac
fi
