# === MODULE_BUILD ===
# id: pubskill_release_builder
#   module_name: build_release
#   module_kind: instrument
#   summary: builds normalized immutable wheel and sdist artifacts from a clean exact Git commit
#   owner: The Interdependency
#   public_surface: python tools/build_release.py --out DIRECTORY
#   internal_surface: normalize_sdist, normalize_wheel, main
#   auth_boundary: none
#   storage_boundary: write
#   storage_notes: temporary build directory and explicit output directory
#   network_boundary: none
#   network_notes: build dependencies must already be installed
#   user_data_boundary: none
#   admin_only: false
#   tests: clean-install repository suite and two-build digest comparison documented in README
#   rollout: explicit release build command
#   rollback: return to previous published immutable release
# === END MODULE_BUILD ===
# === CONTRACTS ===
# id: release_build_binds_exact_source
#   given: a clean source checkout and the pinned build toolchain
#   then: artifacts derive only from Git HEAD; the manifest records source, doctrine, toolchain and output digests
#   class: provenance
# === END CONTRACTS ===

"""Usage: install requirements-build.txt, then run with --out /tmp/release.

Run twice into separate empty directories and compare wheel/sdist SHA-256 values.
The builder performs no publication. Clean-install and consumer gates are required
before publishing these bytes. Archive headers, order, and permissions are
normalized to the commit timestamp. Wheel payloads and RECORD are unchanged.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile


def normalize_sdist(path: Path, destination: Path, epoch: int) -> None:
    with path.open("rb") as raw, tarfile.open(fileobj=raw, mode="r:gz") as source:
        with destination.open("wb") as output, gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
                for member in sorted(source.getmembers(), key=lambda item: item.name):
                    if not (member.isfile() or member.isdir()):
                        raise ValueError(f"unexpected sdist member: {member.name}")
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    member.mtime = epoch
                    member.pax_headers = {}
                    member.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
                    if member.isfile():
                        with source.extractfile(member) as stream:
                            target.addfile(member, stream)
                    else:
                        target.addfile(member)


def normalize_wheel(path: Path, destination: Path, epoch: int) -> None:
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(destination, "w") as target:
        for member in sorted(source.infolist(), key=lambda item: item.filename):
            normalized = zipfile.ZipInfo(member.filename, time.gmtime(epoch)[:6])
            normalized.create_system = 3
            mode = 0o40755 if member.is_dir() else 0o100755 if (member.external_attr >> 16) & 0o111 else 0o100644
            normalized.external_attr = (mode << 16) | (0x10 if member.is_dir() else 0)
            target.writestr(normalized, source.read(member), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    if git("status", "--porcelain"):
        raise SystemExit("release build requires a clean Git checkout")
    commit = git("rev-parse", "HEAD")
    epoch = int(git("show", "-s", "--format=%ct", commit))
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit("release output directory must be empty")
    versions = {}
    for requirement in (root / "requirements-build.txt").read_text().splitlines():
        name, version = requirement.split("==")
        versions[name] = importlib.metadata.version(name)
        if versions[name] != version:
            raise SystemExit(f"build toolchain mismatch: {name}")
    with tempfile.TemporaryDirectory(prefix="pubskill-release-") as directory:
        temporary = Path(directory)
        source = temporary / "source"
        source.mkdir()
        archive = subprocess.check_output(["git", "-C", str(root), "archive", commit])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
            for member in tree.getmembers():
                if member.name.startswith("/") or ".." in Path(member.name).parts or not (member.isfile() or member.isdir()):
                    raise ValueError("unsafe source archive")
            tree.extractall(source)
        environment = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch), PYTHONHASHSEED="0")
        environment.pop("PYTHONPATH", None)
        subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--outdir", str(temporary / "dist"), str(source)], check=True, env=environment)
        for artifact in sorted((temporary / "dist").iterdir()):
            if artifact.name.endswith(".tar.gz"):
                normalize_sdist(artifact, out / artifact.name, epoch)
            elif artifact.suffix == ".whl":
                normalize_wheel(artifact, out / artifact.name, epoch)
            else:
                raise ValueError(f"unexpected build artifact: {artifact.name}")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(out.iterdir())}
    doctrine = json.loads((root / "src/pubskill_lib/_source.json").read_text())
    manifest = {"schema": "pubskill-lib.release-manifest", "version": 1, "source_commit": commit, "source_tree": git("rev-parse", "HEAD^{tree}"), "source_date_epoch": epoch, "skill_lib_commit": doctrine["commit"], "build_toolchain": versions, "build_python": sys.version, "artifacts_sha256": hashes}
    receipt = out / "release-manifest.json"
    receipt.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    hashes = dict(hashes)
    hashes[receipt.name] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    (out / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
