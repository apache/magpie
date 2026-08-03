<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Use the next compat-core API in the widget adapter

Diff:

```diff
--- a/packages/widget-adapter/pyproject.toml
+++ b/packages/widget-adapter/pyproject.toml
@@
dependencies = [
    "compat-core>=1.8.0,<2.0.0",
    "query-base==2.0.0",
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

- `FeatureUnavailable` is first exported by `compat-core` 2.0.0.
- The direct `widget-adapter` requirement creates the mandatory path
  `compat-core>=1.8.0,<2.0.0`.
- `query-base` 2.0.0 creates a second mandatory path by declaring
  `compat-core>=2.0.0`.
- No `compat-core` version can satisfy both paths, so their effective
  intersection is empty in every supported environment.
- The supplied metadata proves the constraint conflict but does not enumerate
  the available `compat-core` releases, so metadata coverage is partial.

Repository dependency and release policy:

- Packages are released independently.
- When a direct dependency range conflicts with a mandatory transitive path
  and changed code uses an API introduced at that transitive lower bound,
  update the direct requirement to that lower bound and remove any obsolete
  upper cap.
