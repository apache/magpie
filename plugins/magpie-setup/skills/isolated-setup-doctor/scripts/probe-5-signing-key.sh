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

if [ "$(git config --get gpg.format)" != "ssh" ]; then
  echo "PROBE: signing-key → ⊘ (gpg.format is not ssh)"
else
  key="$(git config --get user.signingkey)"
  case "$key" in
    "")    echo "PROBE: signing-key → ⊘ (gpg.format=ssh but user.signingkey unset)" ;;
    ssh-*) echo "PROBE: signing-key → ✓ (user.signingkey is a literal key, nothing to read)" ;;
    *)
      key="${key/#\~/$HOME}"
      if head -c 1 "$key" >/dev/null 2>"${TMPDIR:-/tmp}/signing-key.err"; then
        echo "PROBE: signing-key → ✓ ($key readable inside sandbox)"
      else
        echo "PROBE: signing-key → ✗ ($key not readable inside sandbox: $(head -1 "${TMPDIR:-/tmp}/signing-key.err"))"
      fi ;;
  esac
fi
# The touch overlay's wrapper, when git is pointed at it: git inside the
# sandbox reads the same global config and has to be able to start it.
prog="$(git config --get gpg.ssh.program || git config --get gpg.program)"
if [ -n "$prog" ]; then
  prog="${prog/#\~/$HOME}"
  if head -c 1 "$prog" >/dev/null 2>&1; then
    echo "PROBE: signing-program → ✓ ($prog readable inside sandbox)"
  else
    echo "PROBE: signing-program → ✗ ($prog not readable inside sandbox — every sandboxed signed commit fails with 'cannot exec')"
  fi
fi
