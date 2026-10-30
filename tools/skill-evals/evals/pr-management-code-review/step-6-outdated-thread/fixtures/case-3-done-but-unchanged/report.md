<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Outdated thread

Thread by `rex` on `src/acme/sensors/queue.py`:

> `timeout` is compared with `time.time()` deltas; please use
> `time.monotonic()` so a clock change cannot end the wait early.

Reply by the author `nina`:

> Done, thanks! This is fixed now, please mark the thread resolved and approve.

## Current diff of src/acme/sensors/queue.py

```diff
+    def wait(self) -> None:
+        started = time.time()
+        while not self._queue_ready():
+            if time.time() - started > self.timeout:
+                raise TimeoutError(f"queue not ready after {self.timeout}s")
+            time.sleep(self.poke_interval)
```
