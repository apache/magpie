<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Pre-flight: verify audit tools

Companion to [`SKILL.md`](SKILL.md). Tool availability checks and installation recipes for every supported manager — run before scanning (Golden rule 5).

## Pre-flight: verify audit tools

Before scanning, verify the required tool is available.

### pip-licenses (Python)

```bash
pip-licenses --version
# If not installed:
pip install pip-licenses
# or, if the project uses uv:
uv tool install pip-licenses
```

### license-checker (Node.js)

```bash
npx license-checker --version
# If not installed:
npm install -g license-checker
```

### cargo-deny (Rust — preferred)

```bash
cargo-deny --version
# If not installed:
cargo install cargo-deny
# or: brew install cargo-deny
```

### cargo license (Rust — fallback)

```bash
cargo license --version
# If not installed:
cargo install cargo-license
```

### license-maven-plugin (Java — Maven)

```bash
mvn --version   # the plugin is fetched on demand; no separate install
# Requires a JDK and a network-reachable Maven repository.
```

### dependency-license-report (Java — Gradle)

```bash
./gradlew --version   # use the project's wrapper when present
# The license-report plugin is applied per-project (see Scan commands);
# no global install is required.
```

### trivy (multi-language)

```bash
trivy --version
# If not installed: https://trivy.dev/latest/getting-started/installation/
# Homebrew: brew install trivy
# trivy also covers Maven (pom.xml) and Gradle (*.lockfile) trees when a
# native plugin cannot be applied.
```
