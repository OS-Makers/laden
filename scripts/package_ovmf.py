#!/usr/bin/env python3
"""Export a finished firmware build, its provenance and redistribution notices."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(source, destination):
    source, destination = source.resolve(), destination.resolve()
    fv = source / "Build/OvmfX64/DEBUG_GCC5/FV"
    names = ["OVMF_CODE.fd", "OVMF_VARS.fd"]
    for name in names:
        if not (fv / name).is_file() or (fv / name).stat().st_size == 0:
            raise RuntimeError(f"Missing completed firmware output: {fv / name}")
    if sum((fv / name).stat().st_size for name in names) != 4 * 1024 * 1024:
        raise RuntimeError("Expected the matching 4 MiB CODE/VARS pair")
    image_source = source / "MdeModulePkg/Core/Dxe/Image/Image.c"
    if "LADEN_DEBUG_RENDEZVOUS" not in image_source.read_text():
        raise RuntimeError("Checkout does not contain the debug rendezvous patch")

    revision = git(source, "rev-parse", "HEAD")
    patch = git(
        source, "diff", "--",
        "MdeModulePkg/Core/Dxe/Image/Image.c",
        "OvmfPkg/OvmfPkgX64.dsc",
    ) + "\n"
    submodules = {}
    modules = git(source, "config", "--file", ".gitmodules", "--get-regexp", "path")
    for line in modules.splitlines():
        path = line.split(maxsplit=1)[1]
        if (source / path / ".git").exists():
            submodules[path] = git(source / path, "rev-parse", "HEAD")

    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copyfile(fv / name, destination / name)
    (destination / "laden-rendezvous.patch").write_text(patch)

    notices = destination / "licenses"
    if notices.exists():
        shutil.rmtree(notices)
    roots = [source, source / "OvmfPkg"] + [source / path for path in submodules]
    patterns = ["LICENSE*", "License*", "COPYING*", "NOTICE*"]
    for root in roots:
        for pattern in patterns:
            for item in root.glob(pattern):
                if item.is_file():
                    output = notices / item.relative_to(source)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(item, output)

    manifest = {
        "firmware_id": "ovmf-laden-debug-v1",
        "edk2_revision": revision,
        "submodules": submodules,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "gcc": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
        "build": "X64 DEBUG GCC5 FD_SIZE_4MB SECURE_BOOT_ENABLE=FALSE SMM_REQUIRE=FALSE",
        "basetools_extra_flags": "-Wno-error=unused-but-set-variable",
        "image_timestamp_marker": "0x4C414445",
        "patch_sha256": digest(destination / "laden-rendezvous.patch"),
        "images": {name: {"bytes": (destination / name).stat().st_size,
                           "sha256": digest(destination / name)} for name in names},
        "validation": "Built outputs packaged; QEMU/GDB smoke test must be recorded separately",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    files = sorted(path for path in destination.rglob("*")
                   if path.is_file() and path.name != "SHA256SUMS")
    sums = "".join(f"{digest(path)}  {path.relative_to(destination).as_posix()}\n" for path in files)
    (destination / "SHA256SUMS").write_text(sums)
    print(f"Packaged {len(files)} files in {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    package(args.source, args.destination)
