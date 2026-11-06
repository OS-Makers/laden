#!/usr/bin/env python3
"""Add a debugger rendezvous to a private EDK2 checkout, not the application."""
from pathlib import Path
import sys

# A debug-only PE timestamp marker, also set in .cargo/config.toml.
MARKER = 0x4C414445

HOOK = r'''
    // LADEN_DEBUG_RENDEZVOUS: debug firmware only.
    // The host debugger releases the volatile stack gate before application entry.
    if (Image->ImageContext.ImageType == EFI_IMAGE_SUBSYSTEM_EFI_APPLICATION) {
      EFI_IMAGE_DOS_HEADER  *LadenDos;
      EFI_IMAGE_NT_HEADERS64 *LadenNt;
      volatile UINT32       LadenGate;

      LadenDos = (EFI_IMAGE_DOS_HEADER *)Image->Info.ImageBase;
      LadenNt  = (EFI_IMAGE_NT_HEADERS64 *)((UINT8 *)LadenDos + LadenDos->e_lfanew);
      if ((LadenDos->e_magic == EFI_IMAGE_DOS_SIGNATURE) &&
          (LadenNt->Signature == EFI_IMAGE_NT_SIGNATURE) &&
          (LadenNt->FileHeader.TimeDateStamp == 0x4C414445)) {
        LadenGate = 1;
        DEBUG ((DEBUG_ERROR,
          "LADEN_DEBUG BASE=%p ENTRY=%p GATE=%p\n",
          Image->Info.ImageBase, (VOID *)(UINTN)Image->EntryPoint,
          (VOID *)(UINTN)&LadenGate));
        while (LadenGate != 0) {
          CpuPause ();
        }
      }
    }
'''


def patch(path):
    data = Path(path).read_bytes()
    text = data.decode()
    if "LADEN_DEBUG_RENDEZVOUS" in text:
        return
    newline = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")
    anchor = "    Image->Status  = Image->EntryPoint (ImageHandle, Image->Info.SystemTable);"
    if text.count(anchor) != 1:
        raise ValueError("Unexpected EDK2 source; refusing to patch a different location")
    if "#include <IndustryStandard/PeImage.h>" not in text:
        text = '#include <IndustryStandard/PeImage.h>\n' + text
    text = text.replace(anchor, HOOK + anchor)
    Path(path).write_bytes(text.replace("\n", newline).encode())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: patch_ovmf.py <edk2-checkout>")
    patch(Path(sys.argv[1]) / "MdeModulePkg/Core/Dxe/Image/Image.c")
