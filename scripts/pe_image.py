"""Minimal checked PE32+ metadata reader shared by the launcher and GDB."""
from pathlib import Path
import struct

MARKER = 0x4C414445


def parse_pe(data):
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("Not a PE image (missing DOS header)")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Invalid PE header")
    machine, count, stamp, symtab, nsyms, opt_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    opt = pe + 24
    if machine != 0x8664 or opt_size < 112 or opt + opt_size > len(data):
        raise ValueError("Expected an x86_64 PE32+ image")
    if struct.unpack_from("<H", data, opt)[0] != 0x20B:
        raise ValueError("Expected PE32+")
    entry = struct.unpack_from("<I", data, opt + 16)[0]
    base = struct.unpack_from("<Q", data, opt + 24)[0]
    size = struct.unpack_from("<I", data, opt + 56)[0]
    table = opt + opt_size
    if table + count * 40 > len(data):
        raise ValueError("Truncated section table")
    strings = symtab + nsyms * 18 if symtab else 0
    sections = []
    for i in range(count):
        start = table + i * 40
        name = data[start:start + 8].split(b"\0", 1)[0]
        if name.startswith(b"/") and strings:
            offset = strings + int(name[1:])
            if not 0 <= offset < len(data):
                raise ValueError("Invalid COFF section name")
            name = data[offset:].split(b"\0", 1)[0]
        sections.append(name.decode("ascii"))
    return {"image_base": base, "entry_rva": entry, "size": size,
            "timestamp": stamp, "sections": sections}


def read_pe(path):
    return parse_pe(Path(path).read_bytes())
