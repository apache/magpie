<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Outdated thread

Thread by `rex` on `src/acme/hooks/store.py`:

> If `fetch` raises here the temporary directory is never removed.
> Please clean it up in a `finally` block.

## Current diff of src/acme/hooks/store.py

```diff
+    def download(self, key: str) -> bytes:
+        workdir = tempfile.mkdtemp(prefix="store-")
+        # Fetch into a scratch directory first.
+        path = self._client.fetch(key, into=workdir)
+        data = Path(path).read_bytes()
+        shutil.rmtree(workdir)
+        return data
```

The method was renamed from `get` to `download` in the latest push.
