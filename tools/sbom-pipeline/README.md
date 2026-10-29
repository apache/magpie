<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [tools/sbom-pipeline/](#toolssbom-pipeline)
  - [Prerequisites](#prerequisites)
  - [Why a contract](#why-a-contract)
  - [The rules](#the-rules)
    - [1. Format and granularity](#1-format-and-granularity)
    - [2. The subject](#2-the-subject)
    - [3. Components](#3-components)
    - [4. Assemblies](#4-assemblies)
    - [5. Reproducibility](#5-reproducibility)
    - [6. Distribution](#6-distribution)
    - [7. Source releases](#7-source-releases)
  - [Operations](#operations)
  - [Conformance checks](#conformance-checks)
  - [Adapters](#adapters)
  - [Adding an adapter](#adding-an-adapter)
  - [Configuration](#configuration)
  - [Consumers](#consumers)
  - [Open questions](#open-questions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# tools/sbom-pipeline/

**Capability:** contract:sbom-pipeline

**Kind:** interface

**Vendor:** agnostic

This file defines the contract for an **SBOM pipeline**:
the part of a project's build that produces a Software Bill of Materials
for every artifact the project distributes.
Each build ecosystem (Maven, Gradle, npm / Yarn / pnpm, Python, Go, Rust) has its own SBOM generators,
and each generator fills the CycloneDX format in its own way.
The contract states what every SBOM must say,
regardless of the ecosystem and the generator that produced it.
It takes **no position on which generator a project uses**:
each adapter describes an ecosystem,
what any generator used there has to be configured to say,
and what has to be added after it runs;
the generators an adapter names are existing examples, not requirements.

The contract is about integrating SBOM generation into a project's build, once.
It is not a release step:
a project that satisfies it produces conformant SBOMs on every build,
and the release skills only find them there.

## Prerequisites

- **Runtime:** None of its own — this file is a contract *specification* (pure Markdown).
  Concrete prerequisites belong to each ecosystem adapter.
- **CLIs:** None for the contract itself;
  the SBOM generator is the project's choice, and each adapter names known examples for its ecosystem.
- **Credentials / auth:** None.
- **Network:** None for the contract;
  generators resolve dependencies through the ecosystem's own registry during the build.

## Why a contract

An SBOM is useful to the extent that someone outside the project can read it.
Within one ecosystem,
the ecosystem's own metadata (a POM, a `package-lock.json`, a lock file)
already tells its tools most of what an SBOM would.
The value of an SBOM is where ecosystems meet:
a consumer in one ecosystem reading what an artifact from another contains,
and a vulnerability scanner or policy tool that reads every ecosystem the same way.

That only works when the SBOMs mean the same thing, whatever produced them.
Generators disagree on exactly the points that matter across ecosystems:
how the artifact itself is described,
whether a component carries a package URL,
how licenses are expressed,
and above all what happens to content from another ecosystem bundled into the artifact,
which a generator for the artifact's own ecosystem does not see at all.
The contract fixes those points;
the adapters say how to reconcile a generator's output with it.

## The rules

### 1. Format and granularity

Every SBOM is a **CycloneDX 1.7** document in **JSON**.

There is **one SBOM per distributable artifact**:
each package the project publishes to an ecosystem registry
(a Maven JAR or WAR, an npm package, a wheel, a Go module, a crate)
or to its download area,
and the source release itself
(see [Source releases](#7-source-releases)).
An SBOM describes exactly one artifact;
a project does not publish one combined SBOM for everything it builds,
and an artifact's SBOM does not depend on any other SBOM to be complete
(see [Assemblies](#4-assemblies)).

### 2. The subject

`metadata.component` describes the artifact the SBOM belongs to:

- `type`, `name` and `version` of the artifact;
- a `purl` in the artifact's own ecosystem
  (`pkg:maven/…`, `pkg:npm/…`, `pkg:pypi/…`, `pkg:golang/…`, `pkg:cargo/…`);
- `licenses`, as an SPDX license expression;
- the project's organization as `supplier`,
  taken from the project's configuration rather than written into the build by hand,
  so every artifact of the project names its supplier the same way.

`metadata.lifecycles` records the `build` phase:
the SBOM is produced from the build that produced the artifact,
not from a scan of the source tree.

### 3. Components

Every component in a package's SBOM carries:

- a `bom-ref` unique within the document;
- `name`, and a `version`
  (or, for an external component, a `versionRange`; see [Assemblies](#4-assemblies));
- a `purl` whenever its ecosystem has a package-URL type;
- `licenses`, as an SPDX license expression or SPDX license ID,
  whenever the ecosystem's metadata declares one;
- `hashes` whenever the generator has the artifact the component was resolved to.

The `dependencies` graph covers every component in the document, nested ones included,
and only components that ship in the artifact or are required to run it appear in it.
Build-only and test-only dependencies are left out,
or marked `scope: excluded` when an ecosystem's generator cannot leave them out.

### 4. Assemblies

Every component is either **embedded**,
physically contained in the artifact,
or **external**,
required at runtime but provided by the environment the artifact is deployed in.
The SBOM records the difference with the component's `isExternal` flag,
and with where the component sits in the document:

- **Components of the artifact itself** are listed in the top-level `$.components`.
  An embedded one leaves `isExternal` at its default, `false`;
  an external one has `isExternal: true`.
- **Components of an embedded component** form an **assembly**:
  what that component embeds is listed in its own nested `components` array,
  with `isExternal` left at `false`.
  What it requires externally is **not** nested:
  it is listed in the top-level `$.components` with `isExternal: true`,
  because the requirement passes up to the artifact that contains the component.
  The `dependencies` graph still records the external requirement on the component that has it.

So `isExternal: true` appears only in the top-level `$.components`,
which lists, for the whole artifact, everything the environment has to provide.
An external component may give the versions it accepts as a `versionRange` instead of a `version`.

The case the contract exists for is content from another ecosystem.
A JavaScript UI bundled into a WAR is an embedded component of the WAR,
the npm packages bundled into that UI are nested under the UI component,
and the servlet API that the WAR's container provides is external:

```text
metadata.component          pkg:maven/org.example/app-web@1.2.0?type=war
components[]
├─ app-ui                   pkg:npm/%40example/app-ui@1.2.0
│  └─ components[]
│     ├─ react              pkg:npm/react@19.1.0
│     └─ …
├─ commons-lang3            pkg:maven/org.apache.commons/commons-lang3@3.18.0   (WEB-INF/lib)
└─ jakarta.servlet-api      pkg:maven/jakarta.servlet/jakarta.servlet-api@6.1.0  isExternal: true
```

The embedded content is described **in the SBOM itself**,
not by a reference to an SBOM published in the other ecosystem:
a consumer must be able to read an artifact's full contents from that artifact's SBOM alone,
without knowing how to find or fetch SBOMs in an ecosystem it does not use.
The ecosystem that produced the embedded content generates its part with its own adapter,
and the pipeline grafts that part into the container's SBOM
(see [`embed`](#operations)).

The same rule applies within one ecosystem
whenever content is copied into the artifact rather than resolved by the consumer:
classes shaded into a JAR, vendored Go modules, a native library inside a wheel.

### 5. Reproducibility

Two builds of the same source produce the same SBOM, byte for byte,
so the SBOM can be part of a reproducible-build comparison:

- `serialNumber` is a name-based UUID (version 5) derived from the subject's `purl`,
  not a random one,
  and `version` is `1`;
- `metadata.timestamp` is taken from `SOURCE_DATE_EPOCH`;
- arrays are sorted by `bom-ref`,
  and nothing host-specific (absolute paths, user names, tool cache locations) is recorded.

The serial number departs from a recommendation of the specification,
which says every SBOM *should* have a unique serial number
even when its contents have not changed.
The contract trades that for reproducibility,
and follows the specification's own model of identity instead:
the serial number identifies *the SBOM of one artifact version*,
and a corrected SBOM for the same artifact keeps the serial number and increments `version`.

### 6. Distribution

An SBOM is published **next to its artifact, through the artifact's own channel**,
so a consumer finds it where they found the artifact.
Each adapter declares the channel for its ecosystem
(for example, the `cyclonedx` classifier on a Maven artifact,
or the SBOM directory of a wheel's `.dist-info`).
An artifact published to the project's download area carries its SBOM beside it,
with the same checksums and signature as the artifact.

### 7. Source releases

The source release is a distributable artifact too, and has an SBOM of its own.
Where a package's SBOM records the packages it contains,
the source SBOM records the **files** that do not share the project's terms:
every file in the source release whose license or copyright attribution
differs from the project's own is a component, with

- `type: file`, and the file's path within the source release as its `name`;
- `hashes` of the file;
- `licenses`, as an SPDX license expression,
  and `copyright`, as stated for that file.

Files that came into the source tree together (a copied third-party library)
may be nested as an assembly under a component describing where they came from,
with that component's `purl` and `version` when it has them;
each file is still listed.
Files under the project's own license and copyright are not listed:
the subject's `licenses` and `supplier` already cover them.

`metadata.lifecycles` records the `pre-build` phase:
the source SBOM describes the source, not a build of it.

No ecosystem's metadata records the license and copyright of individual files,
but a project that follows its release policy already has that data:
the release's `LICENSE` file names the bundled files under other licenses,
and its `NOTICE` file carries the copyright attributions they require.
The source SBOM is their machine-readable counterpart,
produced from them and required to agree with them.
A project may also check them against the files' headers,
or with a license scanner of its choice;
as for package SBOMs, the contract fixes what the source SBOM says,
not which tool produces it.

## Operations

A pipeline built on the contract runs the steps below;
each adapter implements the ones that are ecosystem-specific.

| Operation                  | Ecosystem-specific | What it does                                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `detect(checkout)`         | yes                | Finds the ecosystem's build files and the distributable artifacts they produce.                                                                                                                                                                                                                                                                              |
| `configure(artifact)`      | yes                | The one-time change to the build: adds and configures a generator of the project's choice, or configures the one it already uses.                                                                                                                                                                                                                            |
| `generate(artifact)`       | yes                | Runs during the build and writes the artifact's SBOM.                                                                                                                                                                                                                                                                                                        |
| `generate-source(release)` | no                 | Writes the source release's SBOM from its `LICENSE` and `NOTICE` files ([Source releases](#7-source-releases)).                                                                                                                                                                                                                                              |
| `embed(container, part)`   | no                 | Grafts the SBOM of embedded content into the container's SBOM ([Assemblies](#4-assemblies)): the part's embedded components are nested under the component that contains them, its external components are moved to the top-level `$.components` (merged with the ones already there), `bom-ref`s are kept unique, and the `dependencies` graphs are merged. |
| `normalize(sbom)`          | no                 | Applies what generators do not: supplier, serial number, timestamp, ordering ([Reproducibility](#5-reproducibility)).                                                                                                                                                                                                                                        |
| `validate(sbom)`           | no                 | Runs the [conformance checks](#conformance-checks).                                                                                                                                                                                                                                                                                                          |
| `publish(artifact, sbom)`  | yes                | Attaches the SBOM to the artifact through the ecosystem's channel ([Distribution](#6-distribution)).                                                                                                                                                                                                                                                         |

`embed`, `normalize` and `validate` are the same for every ecosystem,
and are implemented once, by a deterministic tool,
not by each adapter.
`generate-source` is the same for every ecosystem too:
it reads the release's `LICENSE` and `NOTICE`,
which every release carries whatever its ecosystem.

## Conformance checks

`validate` reports each check as passed, failed, or for review,
with the offending `bom-ref`:

| ID  | Check                                                                                                                                                                                                   |
|-----|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| C1  | The document validates against the CycloneDX 1.7 JSON schema.                                                                                                                                           |
| C2  | `metadata.component` has a `type`, `name`, `version`, `purl`, `licenses` and `supplier`, and the supplier matches the project's configuration.                                                          |
| C3  | Every component has a `bom-ref`, a `name`, and a `version` (or, if external, a `versionRange`; a file in a source SBOM has neither), and every `bom-ref` is unique.                                     |
| C4  | Every component of an ecosystem with a package-URL type has a `purl`.                                                                                                                                   |
| C5  | Every `licenses` entry is a valid SPDX expression or SPDX license ID; a named license (`license.name`, not on the SPDX list) is reported for review.                                                    |
| C6  | Every `bom-ref` named in `dependencies` exists in the document, and in a package SBOM every component appears in `dependencies`.                                                                        |
| C7  | `serialNumber` is the version 5 UUID derived from the subject's `purl`, and `metadata.timestamp` matches `SOURCE_DATE_EPOCH`.                                                                           |
| C8  | No nested component has `isExternal: true`, and every component that a nested component depends on in `dependencies` is either nested in the same assembly or external in the top-level `$.components`. |
| C9  | In a package SBOM, every embedded component in the top-level `$.components` has the same `purl` type as the subject.                                                                                    |
| C10 | In a source SBOM, every file component has `hashes`, `licenses` and `copyright`, and every license other than the project's own appears in the release's `LICENSE` file.                                |

C9 and the `LICENSE` half of C10 are heuristics, reported for review, not as failures.
An embedded component from another ecosystem at the top level (C9)
is usually one whose own SBOM was flattened instead of grafted as an assembly,
but some are legitimate (a native library copied into a wheel).
A `LICENSE` file (C10) names licenses in prose,
which does not always match an SPDX identifier.

## Adapters

One adapter per ecosystem, under `tools/sbom-pipeline-<ecosystem>/`.
The generators below are examples of existing tools for each ecosystem, not requirements:
a project uses whichever it prefers,
and one that already produces SBOMs keeps its generator
and adds only what `normalize` has to fill in.

| Adapter  | Status  | Example generators                                             | Notes                                                                      |
|----------|---------|----------------------------------------------------------------|----------------------------------------------------------------------------|
| `maven`  | planned | `org.cyclonedx:cyclonedx-maven-plugin`                         | Many ASF projects already inherit this one from the ASF parent POM.        |
| `gradle` | planned | `org.cyclonedx.bom` Gradle plugin                              |                                                                            |
| `js`     | planned | `@cyclonedx/cyclonedx-npm`, `@cyclonedx/yarn-plugin-cyclonedx` | One adapter for npm, Yarn and pnpm; they share the `npm` package-URL type. |
| `python` | planned | `cyclonedx-py`                                                 | The SBOM goes into the wheel's `.dist-info/sboms/` (PEP 770).              |
| `go`     | planned | `cyclonedx-gomod`                                              |                                                                            |
| `rust`   | planned | `cargo-cyclonedx`                                              |                                                                            |

Whether each generator emits CycloneDX 1.7 natively is recorded per adapter;
one that does not yet is upgraded by `normalize`,
and the adapter says so.

## Adding an adapter

An adapter README declares, for its ecosystem:

- how `detect` recognizes the ecosystem and its distributable artifacts;
- the generators it knows of, each with the version the adapter was checked against,
  and the build-file change `configure` makes for each;
- for each rule above and each generator, which fields the generator fills
  and which `normalize` has to fill instead;
- how a part from this ecosystem is produced
  when it is embedded in another ecosystem's artifact;
- the `publish` channel.

## Configuration

The contract reads one value from the adopting project's configuration
(`<project-config>/project.md`, else its organization, else the framework default):
the **supplier** written into every SBOM's `metadata.component` and checked by C2.
Which key holds it is not settled yet
(see [Open questions](#open-questions)).
Each adapter documents any ecosystem-specific keys it adds.

## Consumers

| Skill                     | Status  | Use                                                                                                                                                                                         |
|---------------------------|---------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `sbom-pipeline-integrate` | planned | Detects every ecosystem in a checkout, applies each adapter's `configure`, wires `generate-source`, `embed`, `normalize` and `validate` into the build, and hands back a commit for review. |
| `sbom-pipeline-verify`    | planned | Read-only: runs `validate` against the SBOMs a build produced.                                                                                                                              |

## Open questions

- **Source release identity.**
  A source release belongs to no package ecosystem,
  so which `purl` type identifies it in the source SBOM's `metadata.component`
  (and so derives its serial number) is not settled.
- **Supplier configuration key.**
  Which key of the project or organization manifest names the supplier;
  an organization-level default (the ASF for every ASF project)
  would let most projects declare nothing.
- **Generator versions.**
  Whether the generator versions an adapter was checked against are recorded in a `registry.json` here,
  as [`hook-manager`](../hook-manager/) does for its adapters,
  or only in each adapter's README.
