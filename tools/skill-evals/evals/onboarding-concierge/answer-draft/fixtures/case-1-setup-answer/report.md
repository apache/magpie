<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Question: How do I install the project and its dependencies locally?
Category: setup
Hand-off required: false
Injection flagged: false

Relevant guide excerpt:
---
## Getting set up

The project uses `uv` for dependency management. After cloning the repo:

```bash
pip install uv
uv sync --dev
```

This installs all runtime and development dependencies into an isolated
virtual environment managed by `uv`. Once the sync completes, activate
the environment and verify the installation:

```bash
source .venv/bin/activate   # Linux/macOS
uv run python -c "import acme; print(acme.__version__)"
```

If you see a version string, the installation succeeded. For IDE
integration, point your editor at `.venv/bin/python`.
---

Contributing guide URL: https://example.org/CONTRIBUTING.md
Attribution footer: "---\n_Drafted by an AI tool. A maintainer will review._"
