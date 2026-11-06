#!/usr/bin/env python3
"""Generate the GDB target from the selected nightly's own built-in target."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
toolchain = os.environ.get("LADEN_DEBUG_TOOLCHAIN", "nightly-2026-03-25")
try:
    spec = json.loads(subprocess.check_output([
        "rustc", f"+{toolchain}", "-Z", "unstable-options", "--print",
        "target-spec-json", "--target", "x86_64-unknown-uefi",
    ], text=True))
    spec["debuginfo-kind"] = "dwarf"
    spec["split-debuginfo"] = "unpacked"
    spec["supported-split-debuginfo"] = ["off", "unpacked"]
    spec.pop("is-builtin", None)
    target = root / "targets/x86_64-unknown-uefi-gdb.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"Created {target}; build with cargo +{toolchain} debug")
except (OSError, subprocess.CalledProcessError, ValueError) as exc:
    sys.exit(f"Cannot prepare debug target: {exc}")
