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

"""Where a project's Magpie configuration lives.

Two layers, personal first:

* **Personal** — gitignored, one user's.  In an *adopted* repository (one
  with a committed `.apache-magpie.lock`) it is `<repo>/.apache-magpie-local/`.
  In a repository that has **not** adopted Magpie it is
  `<git-common-dir>/apache-magpie/`: inside the repository's git directory,
  never in the working tree, so it is never committed, needs no ignore
  entry, and is shared by every worktree of the clone.  In a Subversion
  working copy it is `<.svn>/apache-magpie/` for the same reasons.  With no
  version control at all there is nothing it could be committed to, so it is
  the in-tree `<root>/.apache-magpie-local/`.
  A linked worktree of an adopted repository (`git worktree add`) has no
  `.apache-magpie-local/` of its own, since the directory is gitignored, so
  its main checkout's is read after its own, file by file, and written to
  when the worktree has none (`main_worktree`).
* **Committed** — `<repo>/.apache-magpie-overrides/`, written only by
  `adopt`.  It is read wherever it exists.

An unadopted repository that still carries the old in-tree
`.apache-magpie-local/` keeps working: that directory is read after the
personal layer as a legacy fallback, and the pre-flight reports it so the
user can move it.

Nothing here creates a directory.  A read that created the personal layer
would fake the "configured" state the pre-flight reads from its presence.

The pre-flight checker itself is not installed in the personal layer but
under `checker_home`, a per-user directory outside every project, so that
nothing the opened tree carries, its `.git/` and `.svn/` included, is ever
imported as the checker.  A checker copied from a framework outside the
project goes in `checker_home` itself and serves every project; one copied
from inside the project (a pinned snapshot) goes in that project's own
`project_checker_home` and serves only it (`checker_install_dir`).

Run as a module it prints where each layer is, for a skill that has to
write the personal layer rather than read it:

    python3 -m setup_preflight.layers [--project-root .]

The git common directory is computed by reading files, never by spawning
`git`: the pre-flight runs on every skill invocation, often sandboxed.
The tools under `tools/` that resolve configuration carry an identical copy
of `git_common_dir` and the same test vectors; keep them in step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

LOCK_NAME = ".apache-magpie.lock"
LOCAL_DIR = ".apache-magpie-local"
OVERRIDES_DIR = ".apache-magpie-overrides"
#: The personal layer's name inside the git common directory.
GIT_HOME_NAME = "apache-magpie"


def _absolute(path: Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))


def git_common_dir(root: Path) -> Path | None:
    """The repository's common git directory, or `None` when `root` is not a repo.

    `<root>/.git` a directory → that directory.  A file reading
    `gitdir: <path>` (a linked worktree, or a submodule) → that worktree git
    directory, and then the directory its `commondir` file names (relative
    to the worktree git directory), when it has one.  Relative paths resolve
    against the file that holds them.
    """
    dotgit = _absolute(root) / ".git"
    if dotgit.is_dir():
        return dotgit
    if not dotgit.is_file():
        return None
    try:
        first = dotgit.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    if not first.startswith("gitdir:"):
        return None
    target = first.removeprefix("gitdir:").strip()
    if not target:
        return None
    gitdir = _absolute(dotgit.parent / target)
    if not gitdir.is_dir():
        return None
    commondir = gitdir / "commondir"
    if not commondir.is_file():
        return gitdir
    try:
        common = commondir.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not common:
        return gitdir
    resolved = _absolute(gitdir / common)
    return resolved if resolved.is_dir() else None


def adopted(root: Path) -> bool:
    """Whether the project has adopted Magpie: a committed lock exists."""
    return (root / LOCK_NAME).is_file()


def main_worktree(root: Path) -> Path | None:
    """The main checkout of the linked worktree `root`, or `None`.

    `<root>/.git` a file whose common git directory is named `.git` and is
    the `.git` directory of its parent (a non-bare main checkout) → that
    parent.  `None` for the main checkout itself, a bare repository, a
    submodule, or no repository.  Reads files only, never spawns `git`.

    The main checkout is located from the worktree's `.git` file, which an
    agent able to write the worktree can rewrite.  That only selects
    configuration the agent could already write into the worktree's own
    `.apache-magpie-local/`, so following it grants no new capability.
    """
    if not (_absolute(root) / ".git").is_file():
        return None
    common = git_common_dir(root)
    if common is None or common.name != ".git":
        return None
    main = common.parent
    return main if (main / ".git").is_dir() else None


def svn_admin_dir(root: Path) -> Path | None:
    """`<root>/.svn` when `root` is the root of a Subversion working copy, else `None`.

    Subversion keeps one `.svn`, holding a `wc.db`, at the root of a working
    copy.  Only `root`'s own is accepted, as with `.git`: following one in an
    ancestor would let any directory above the project redirect where its
    configuration is read and written.  Reads files only, never spawns `svn`.
    """
    admin = _absolute(root) / ".svn"
    return admin if (admin / "wc.db").is_file() else None


def unadopted_home(root: Path) -> Path:
    """Where an unadopted project keeps personal configuration; never created here.

    `<git-common-dir>/apache-magpie` in a git repository, else
    `<.svn>/apache-magpie` in a Subversion working copy: both inside the
    VCS's own directory, so never committed.  With no VCS at all there is
    nothing to commit it to, so it is the in-tree `<root>/.apache-magpie-local`.

    A VCS directory is trusted as the home only when it is this user's and
    the only one at the root.  With both a `.git` and a Subversion working
    copy there, one may be versioned content of the other's checkout
    (Subversion versions a `.git/`, git a `.svn/`), so a crafted tree could
    supply configuration where nobody looks; and a directory another user
    owns is one git itself would not trust (`safe.directory`).  Either way
    the home is the in-tree `<root>/.apache-magpie-local`, in plain sight.
    """
    common = git_common_dir(root)
    svn = svn_admin_dir(root)
    admin = common if svn is None else svn if common is None else None
    if admin is None:
        return root / LOCAL_DIR
    getuid = getattr(os, "getuid", None)
    try:
        if getuid is not None and os.stat(admin).st_uid != getuid():
            return root / LOCAL_DIR
    except OSError:
        return root / LOCAL_DIR
    return admin / GIT_HOME_NAME


CHECKER_HOME = Path(".cache") / "apache-magpie" / "preflight"


def checker_home() -> Path:
    """Where the pre-flight checker is installed and imported from: `~/.cache/apache-magpie/preflight`.

    One per-user directory, outside every project.  A directory inside the
    opened tree is never safe to import from, even the VCS's own: Subversion
    versions a `.git/` like any other directory, and a tarball can carry a
    `.git/` or a `.svn/` (with its `wc.db`) that `git` and this module accept
    as real.  So the checker does not depend on which project is open, or on
    whether it has version control at all.  The block names the same path as
    `$HOME/.cache/apache-magpie/preflight`.
    """
    return Path.home() / CHECKER_HOME


def project_key(root: Path) -> str:
    """The project's key under `checker_home() / "projects"`: its resolved path, hashed.

    The block computes the same value inline, as
    `hashlib.sha256(os.path.realpath(os.curdir).encode()).hexdigest()[:16]`.
    """
    return hashlib.sha256(os.path.realpath(root).encode()).hexdigest()[:16]


def project_checker_home(root: Path) -> Path:
    """Where a checker copied from inside `root` is installed: for `root` alone."""
    return checker_home() / "projects" / project_key(root)


ROOT_ID_NAME = "root-id"

# Where an installed framework lives, relative to the user's home: the
# harnesses' plugin installs, and the framework copy the session hook
# materialises.  Nothing a project carries resolves under these.
FRAMEWORK_ROOTS = (
    Path(".claude") / "plugins" / "cache" / "apache-magpie",
    Path(".agents") / "plugins" / "magpie",
    Path(".gemini") / "config" / "plugins",
    Path(".cache") / "apache-magpie" / "framework",
)


def framework_roots() -> list[Path]:
    """The known framework locations under this user's home, unresolved."""
    return [Path.home() / relative for relative in FRAMEWORK_ROOTS]


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def checker_install_dir(root: Path, source: Path) -> Path:
    """Where `config` or `upgrade` may install a checker copied from `source`.

    The shared `checker_home` serves every project, so it takes a copy only
    from a known framework location (`framework_roots`): a harness's plugin
    install, or the framework copy under `~/.cache/apache-magpie/framework/`.
    Anything else — a pinned snapshot inside the project, which a tarball can
    carry too, or any other directory — goes to `project_checker_home(root)`
    and serves that project alone, so a crafted tree reaches no other
    project.  Both sides are resolved first, so a link under a known root
    that points elsewhere does not count; and a source that resolves inside
    the project never qualifies, even through a known root that is itself a
    link into it.
    """
    resolved = os.path.realpath(source)
    if _inside(resolved, os.path.realpath(root)):
        return project_checker_home(root)
    if any(_inside(resolved, os.path.realpath(known)) for known in framework_roots()):
        return checker_home()
    return project_checker_home(root)


def _root_identity(root: Path) -> str:
    st = os.stat(os.path.realpath(root))
    return f"{st.st_dev} {st.st_ino}"


def record_root_identity(root: Path) -> Path:
    """Record `root`'s identity beside its per-project install; returns the file.

    The key is the root's path, which outlives the project: a different tree
    created later at the same path would otherwise import the old install.
    The block and `import_dir` use the per-project copy only while the
    identity (`st_dev`, `st_ino` of the resolved root) still matches.
    """
    own = project_checker_home(root)
    own.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = own / ROOT_ID_NAME
    path.write_text(_root_identity(root) + "\n", encoding="utf-8")
    return path


def import_dir(root: Path) -> Path:
    """The directory the block puts on `PYTHONPATH` in `root`.

    The project's own when it holds a checker installed for this very tree
    (its recorded identity matches), else the shared one.
    """
    own = project_checker_home(root)
    recorded = own / ROOT_ID_NAME
    if (
        (own / "setup_preflight").is_dir()
        and recorded.is_file()
        and recorded.read_text(encoding="utf-8").split() == _root_identity(root).split()
    ):
        return own
    return checker_home()


def personal_dir(root: Path) -> Path:
    """Where this user's configuration for `root` is written; never created here.

    Adopted → `<root>/.apache-magpie-local`, except in a linked worktree
    that has none while its main checkout has one: then the main
    checkout's, so a worktree writes where it already reads.  Not adopted →
    `unadopted_home`.  May not exist yet.
    """
    if adopted(root):
        own = root / LOCAL_DIR
        main = main_worktree(root)
        if own.is_dir() or main is None or not (main / LOCAL_DIR).is_dir():
            return own
        return main / LOCAL_DIR
    return unadopted_home(root)


def personal_layers(root: Path) -> list[Path]:
    """Every personal directory a config file is looked up in, first match wins.

    Adopted → `<root>/.apache-magpie-local`, then, in a linked worktree,
    the main checkout's when it exists: `.apache-magpie-local/` is
    gitignored, so a new worktree has none, and a file missing from its own
    is found in the main checkout's.  Not adopted → `unadopted_home`
    (in git, already shared by every worktree), then a legacy in-tree
    `.apache-magpie-local/`.
    """
    if adopted(root):
        found = [root / LOCAL_DIR]
        main = main_worktree(root)
        if main is not None and (main / LOCAL_DIR).is_dir():
            found.append(main / LOCAL_DIR)
        return found
    found = [unadopted_home(root)]
    legacy = root / LOCAL_DIR
    if legacy.is_dir() and legacy not in found:
        found.append(legacy)
    return found


def legacy_local_dir(root: Path) -> Path | None:
    """The old in-tree personal layer of an unadopted repository, if present.

    With no version control the in-tree directory is the personal layer
    itself, not a leftover, so it is not reported.
    """
    if adopted(root):
        return None
    legacy = root / LOCAL_DIR
    return legacy if legacy.is_dir() and legacy != unadopted_home(root) else None


def config_layers(root: Path) -> list[Path]:
    """Every directory a config file is looked up in, first match wins."""
    return [*personal_layers(root), root / OVERRIDES_DIR]


def resolve(root: Path, name: str) -> Path | None:
    """The first existing `<layer>/<name>`, or `None`."""
    for layer in config_layers(root):
        candidate = layer / name
        if candidate.exists():
            return candidate
    return None


def describe(root: Path) -> dict[str, object]:
    home = personal_dir(root)
    legacy = legacy_local_dir(root)
    main = main_worktree(root)
    checker = checker_home()
    own = project_checker_home(root)
    return {
        "adopted": adopted(root),
        "checker_dir": str(checker),
        "import_dir": str(import_dir(root)),
        "project_checker_dir": str(own),
        "main_worktree": str(main) if main is not None else None,
        "personal_dir": str(home),
        "personal_dir_exists": home.is_dir(),
        "personal_layers": [str(p) for p in personal_layers(root)],
        "legacy_local_dir": str(legacy) if legacy is not None else None,
        "config_layers": [str(p) for p in config_layers(root)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="setup_preflight.layers", description="Print where Magpie config lives."
    )
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument(
        "--install-source",
        type=Path,
        help="print the directory a checker copied from this source may be installed in",
    )
    args = parser.parse_args(argv)
    described = describe(args.project_root)
    if args.install_source is not None:
        described["install_dir"] = str(checker_install_dir(args.project_root, args.install_source))
    print(json.dumps(described, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
