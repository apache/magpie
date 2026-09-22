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

python3 - <<'PY' 2>&1 || true
import socket, urllib.request, threading, http.server, sys

# 1. Can we bind?
try:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.listen(1)
except OSError as e:
    print(f"PROBE: localhost-bind → ✗ (bind: {e})")
    sys.exit(0)

# 2. Can we GET from our own server over loopback?
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *_): pass

server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5) as r:
        body = r.read()
    print(f"PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP {r.status}, body={body!r})")
except Exception as e:
    print(f"PROBE: localhost-bind → ✗ (bind ok, loopback GET: {type(e).__name__}: {e})")
finally:
    server.shutdown()
    s.close()
PY
