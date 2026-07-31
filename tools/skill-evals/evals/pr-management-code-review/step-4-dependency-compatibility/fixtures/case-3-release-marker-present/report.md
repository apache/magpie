<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add client helper to the widget adapter

Diff:

```diff
--- a/packages/widget-adapter/pyproject.toml
+++ b/packages/widget-adapter/pyproject.toml
@@
 dependencies = [
-    "compat-core>=1.8.0",
+    "compat-core>=1.8.0",  # use next version
     "query-base>=1.32.0",
 ]

--- /dev/null
+++ b/packages/widget-adapter/src/widget_adapter/client.py
@@
+from compat_core.exceptions import FeatureUnavailable
+
+def get_client():
+    raise FeatureUnavailable("client support is not installed")
```

Published package metadata:

- `FeatureUnavailable` is first exported by `compat-core` 1.12.0.
- `query-base` 1.32.0 declares the mandatory dependency
  `compat-core>=1.12.0`.
- Both dependencies are installed into the same environment.

Repository dependency and release policy:

- Packages are released independently.
- Contributors must not change inter-package lower bounds directly.
- When changed code starts using a newer API from another package, add the
  exact comment `# use next version` to that direct dependency.
- Release preparation updates the lower bound and removes the marker.
