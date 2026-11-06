"""Executed by GDB after QMP has stopped OVMF at the rendezvous."""
import json
import os
from pathlib import Path
import struct
import sys

import gdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pe_image import MARKER, read_pe


def start():
    path = os.environ["LADEN_EFI"]
    base = int(os.environ["LADEN_BASE"], 16)
    entry = int(os.environ["LADEN_ENTRY"], 16)
    gate = int(os.environ["LADEN_GATE"], 16)
    local = read_pe(path)
    gdb.execute("set pagination off")
    gdb.execute("set confirm off")
    gdb.execute("set tcp auto-retry on")
    gdb.execute("set tcp connect-timeout 10")
    # A private UNIX socket avoids accidentally attaching to another VM.
    gdb.execute("target remote " + os.environ["LADEN_GDB_SOCKET"])
    inferior = gdb.selected_inferior()
    dos = bytes(inferior.read_memory(base, 64))
    if dos[:2] != b"MZ":
        raise gdb.GdbError("Runtime image has no DOS header; gate remains closed")
    pe_offset = struct.unpack_from("<I", dos, 0x3C)[0]
    if pe_offset > 0x100000:
        raise gdb.GdbError("Invalid runtime PE offset; gate remains closed")
    header = bytes(inferior.read_memory(base + pe_offset, 112))
    stamp = struct.unpack_from("<I", header, 8)[0]
    rva = struct.unpack_from("<I", header, 24 + 16)[0]
    size = struct.unpack_from("<I", header, 24 + 56)[0]
    if (header[:4] != b"PE\0\0" or stamp != MARKER or
            rva != local["entry_rva"] or size != local["size"] or entry != base + rva):
        raise gdb.GdbError("Runtime image does not match the built EFI; gate remains closed")
    if bytes(inferior.read_memory(gate, 4)) != b"\x01\x00\x00\x00":
        raise gdb.GdbError("Unexpected firmware gate value")

    slide = base - local["image_base"]
    gdb.execute(f"add-symbol-file {json.dumps(path)} -o {slide}")
    # Exact PE entry address: no symbol-name/prologue ambiguity.
    breakpoint = gdb.Breakpoint(f"*{entry:#x}", type=gdb.BP_HARDWARE_BREAKPOINT, temporary=True)
    inferior.write_memory(gate, struct.pack("<I", 0))
    gdb.write(f"Laden: base={base:#x}, entry={entry:#x}; continuing to application entry.\n")
    gdb.execute("continue")
    pc = int(gdb.parse_and_eval("$pc"))
    if pc != entry:
        gdb.write(f"Stopped at {pc:#x}, before reaching the requested entry.\n")
    else:
        gdb.write("Stopped at laden EFI entry. Use step/next, break file:line, or continue.\n")


start()
