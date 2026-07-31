<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add client helper to the widget adapter

Diff:

```diff
--- a/packages/widget-adapter/pyproject.toml
+++ b/packages/widget-adapter/pyproject.toml
@@
 dependencies = [
     "compat-core>=1.8.0",
     "query-base==1.32.0",
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
  `compat-core>=1.12.0; python_version < "3.12"`.
- The environment marker makes that transitive constraint inactive on Python
  3.12; the direct `compat-core>=1.8.0` requirement still applies there.
- Python 3.11 and Python 3.12 are both supported environments.
- On Python 3.12, `query-base==1.32.0` with `compat-core==1.8.0` is a concrete
  resolution that satisfies every active constraint and lacks
  `FeatureUnavailable`.
- The supplied metadata establishes that concrete resolution only; other
  versions allowed by the declared constraints have not been enumerated.

Repository dependency and release policy:

- Packages are released independently.
- When a supported environment can install a dependency version that lacks an
  API used by changed code, update the direct lower bound to the first version
  that exports the API.
