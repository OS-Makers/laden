#!/usr/bin/env python3
"""QMP controls startup; GDB owns the VM only after the firmware rendezvous."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from pe_image import MARKER, read_pe

RENDEZVOUS = re.compile(r"LADEN_DEBUG BASE=(?:0x)?([0-9a-fA-F]+) ENTRY=(?:0x)?([0-9a-fA-F]+) GATE=(?:0x)?([0-9a-fA-F]+)")


class QMP:
    def __init__(self, path, process, timeout):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        deadline = time.monotonic() + timeout
        while True:
            if process.poll() is not None:
                self.socket.close()
                raise RuntimeError("QEMU exited before QMP was ready; inspect qemu-debug.log")
            try:
                self.socket.connect(str(path))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() >= deadline:
                    self.socket.close()
                    raise TimeoutError("QMP did not become ready")
                time.sleep(0.05)
        self.socket.settimeout(timeout)
        self.stream = self.socket.makefile("rwb")
        if "QMP" not in self.read():
            raise RuntimeError("Missing QMP greeting")
        self.command("qmp_capabilities")

    def read(self):
        line = self.stream.readline()
        if not line:
            raise RuntimeError("QMP connection closed")
        return json.loads(line)

    def command(self, name):
        self.stream.write((json.dumps({"execute": name, "id": name}) + "\n").encode())
        self.stream.flush()
        while True:
            result = self.read()
            if result.get("id") == name:
                if "error" in result:
                    raise RuntimeError(str(result["error"]))
                return result.get("return")

    def close(self):
        self.stream.close()
        self.socket.close()


def wait_for_gate(path, process, timeout):
    deadline = time.monotonic() + timeout
    position = 0
    pending = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("QEMU exited before the debug rendezvous")
        if path.exists():
            with path.open(errors="replace") as log:
                log.seek(position)
                pending += log.read()
                position = log.tell()
            lines = pending.split("\n")
            pending = lines.pop()
            for line in lines:
                match = RENDEZVOUS.search(line)
                if match:
                    return match.groups()
        time.sleep(0.02)
    raise TimeoutError("No firmware rendezvous. Check ovmf-debug.log, debug firmware and PE marker")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--efi", required=True, type=Path)
    parser.add_argument("--logs", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    command = options.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("Missing QEMU command")
    binary = options.efi.resolve()
    info = read_pe(binary)
    if info["timestamp"] != MARKER or ".debug_info" not in info["sections"]:
        raise RuntimeError("Expected a marked DWARF build. Run prepare_debug_target.py and cargo +nightly-2026-03-25 debug")
    gdb = os.environ.get("GDB_BIN", "gdb")
    if not shutil.which(gdb):
        raise RuntimeError(f"Missing debugger: {gdb}")
    # Probe Python support before starting a VM which will wait for it.
    subprocess.run([gdb, "-nx", "-q", "-batch", "-ex", "python import gdb"], check=True)
    timeout = float(os.environ.get("LADEN_DEBUG_TIMEOUT", "90"))
    logs = options.logs.resolve()
    logs.mkdir(parents=True, exist_ok=True)
    firmware_log = logs / "ovmf-debug.log"
    qemu_log = logs / "qemu-debug.log"
    firmware_log.write_text("")
    script = Path(__file__).with_name("gdb_laden.py").resolve()
    with tempfile.TemporaryDirectory(prefix="laden-gdb-", dir="/tmp") as temporary:
        qmp_path = Path(temporary) / "qmp"
        gdb_path = Path(temporary) / "gdb"
        args = command + [
            "-S", "-gdb", f"unix:{gdb_path},server=on,wait=off",
            "-qmp", f"unix:{qmp_path},server=on,wait=off",
            "-debugcon", f"file:{firmware_log}",
            "-global", "isa-debugcon.iobase=0x402",
        ]
        with qemu_log.open("w") as output:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            qmp = None
            try:
                qmp = QMP(qmp_path, process, timeout)
                qmp.command("cont")
                base, entry, gate = wait_for_gate(firmware_log, process, timeout)
                qmp.command("stop")
                status = qmp.command("query-status")
                if status["running"]:
                    raise RuntimeError("QEMU did not stop")
                env = os.environ.copy()
                env.update(LADEN_EFI=str(binary), LADEN_BASE=base, LADEN_ENTRY=entry,
                           LADEN_GATE=gate, LADEN_GDB_SOCKET=str(gdb_path))
                expression = f"exec(compile(open({str(script)!r}).read(), {str(script)!r}, 'exec'), {{'__file__': {str(script)!r}}})"
                print(f"Firmware rendezvous reached. Logs: {logs}", flush=True)
                return subprocess.call([gdb, "-nx", "-q", "-ex", "python " + expression], env=env)
            finally:
                if qmp is not None:
                    qmp.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f"Debug startup failed: {exc}")
