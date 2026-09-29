<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Scan commands

Companion to [`SKILL.md`](SKILL.md). Per-manager scan commands and the JSON/XML fields to parse, run from the repository root.

## Scan commands

Run from the repository root (local checkout or a temporary clone).

### Python — pip-licenses

```bash
pip-licenses --format json --with-urls --with-description \
    --output-file /tmp/dep-lic-pip.json
```

Parse the JSON output: each entry has `Name`, `Version`, `License`, and
`URL`. Normalise the `License` string to an SPDX expression before
classifying (e.g. `MIT License` → `MIT`).

If the project uses `uv`:

```bash
uv run pip-licenses --format json --with-urls --with-description \
    --output-file /tmp/dep-lic-pip.json
```

### Node.js — license-checker

```bash
npx license-checker --json --out /tmp/dep-lic-npm.json
```

Parse the JSON output: each key is `package@version`; the value object
has `licenses` (a string or array) and `licenseFile`.

### Rust — cargo-deny

```bash
cargo-deny --format json check licenses 2>/tmp/dep-lic-cargo-deny.json || true
```

Parse the JSON output: each `deny` or `warn` event has `name`, `version`,
`license`, and the matched policy rule. Use `advisories`, `licenses`, and
`sources` sections.

If `cargo-deny` is not available, fall back to `cargo license`:

```bash
cargo license --json --avoid-build-deps \
    > /tmp/dep-lic-cargo.json
```

Parse the JSON array: each entry has `name`, `version`, and `license`.

### Java — Maven (license-maven-plugin)

```bash
mvn org.codehaus.mojo:license-maven-plugin:2.4.0:aggregate-download-licenses \
    -Dlicense.outputDirectory=/tmp/dep-lic-maven
# The aggregated report is written to
# /tmp/dep-lic-maven/licenses.xml (covers a multi-module reactor).
```

Parse the XML output: each `<dependency>` has `<groupId>`, `<artifactId>`,
`<version>`, and one or more `<license><name>` elements. Normalise each
`<name>` to an SPDX expression before classifying (for example
`The Apache Software License, Version 2.0` → `Apache-2.0`). Maven license
metadata is free text, so expect to normalise more aggressively than for the
Python or Rust ecosystems.

### Java — Gradle (dependency-license-report)

Apply the plugin without editing the checked-in build. Write a throwaway
init script and point Gradle at it so no manifest is modified:

```bash
cat > /tmp/license-report.init.gradle <<'EOF'
initscript {
  repositories { mavenCentral() }
  dependencies { classpath 'com.github.jk1:gradle-license-report:2.9' }
}
allprojects {
  apply plugin: com.github.jk1.license.LicenseReportPlugin
  licenseReport {
    outputDir = '/tmp/dep-lic-gradle'
    renderers = [new com.github.jk1.license.render.JsonReportRenderer()]
  }
}
EOF
./gradlew --init-script /tmp/license-report.init.gradle generateLicenseReport
```

Parse `/tmp/dep-lic-gradle/index.json`: each entry under `dependencies` has
`moduleName` (`group:artifact`), `moduleVersion`, and `moduleLicense` /
`moduleLicenses[]`. Normalise each license name to an SPDX expression before
classifying, as with Maven.

If neither wrapper nor plugin can be applied (no JDK, offline, or a locked
build), fall back to **trivy** below, which reads `pom.xml` and Gradle
`*.lockfile` trees directly.

### Multi-language — trivy

```bash
trivy fs --format cyclonedx --output /tmp/dep-lic-trivy.json .
```

Parse the CycloneDX JSON: `components[]` each has `name`, `version`, and
`licenses[].expression` (SPDX expression).

Alternatively, use the `--scanners license` flag for a simpler output:

```bash
trivy fs --scanners license --format json \
    --output /tmp/dep-lic-trivy.json .
```

