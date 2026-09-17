#!/usr/bin/env python3
"""
Hand-assembles a minimal 16-bit real-mode x86 boot sector, byte by byte.

faSM (https://github.com/Agh0stt/faSM) only assembles 32-bit protected-mode
instructions into ELF32 executables -- it has no BITS 16 / ORG directive and
no 16-bit registers (ax, si, ds, es, ss, sp, ...). A classic BIOS boot sector
needs 16-bit real-mode code, so this script computes the exact machine code
bytes by hand (registers, addressing, and jump displacements all resolved
manually) and writes them to bootcode.bin. gen_fasm_source.py then wraps
those bytes as `db` directives so faSM can emit them verbatim.
"""

code = bytearray()


def emit(*bs):
    code.extend(bs)


off = {}

off['start'] = len(code)
emit(0x31, 0xC0)              # xor ax, ax
emit(0x8E, 0xD8)               # mov ds, ax
emit(0x8E, 0xC0)                # mov es, ax
emit(0x8E, 0xD0)                 # mov ss, ax
emit(0xBC, 0x00, 0x7C)            # mov sp, 0x7C00

msi_pos = len(code)
emit(0xBE, 0x00, 0x00)              # mov si, msg (placeholder, patched below)

off['print'] = len(code)
emit(0xAC)                            # lodsb
emit(0x08, 0xC0)                       # or al, al
jz_pos = len(code)
emit(0x74, 0x00)                        # jz .halt (placeholder rel8)
emit(0xB4, 0x0E)                         # mov ah, 0x0E
emit(0xB7, 0x00)                          # mov bh, 0x00
emit(0xCD, 0x10)                           # int 0x10
jmp_print_pos = len(code)
emit(0xEB, 0x00)                            # jmp .print (placeholder rel8)

off['halt'] = len(code)
emit(0xFA)                                    # cli
emit(0xF4)                                     # hlt
jmp_halt_pos = len(code)
emit(0xEB, 0x00)                                # jmp .halt (placeholder rel8)

off['msg'] = len(code)
msg = b"Hello from a working bootloader!\r\n\x00"
code.extend(msg)

# Patch absolute address of msg (segment 0, loaded at 0x7C00 + offset).
msg_addr = 0x7C00 + off['msg']
code[msi_pos + 1] = msg_addr & 0xFF
code[msi_pos + 2] = (msg_addr >> 8) & 0xFF

# Patch relative jumps: rel8 = target - address_after_instruction.
code[jz_pos + 1] = (off['halt'] - (jz_pos + 2)) & 0xFF
code[jmp_print_pos + 1] = (off['print'] - (jmp_print_pos + 2)) & 0xFF
code[jmp_halt_pos + 1] = (off['halt'] - (jmp_halt_pos + 2)) & 0xFF

with open("bootcode.bin", "wb") as f:
    f.write(code)

print(f"code length: {len(code)} bytes")
print("offsets:", off)
print(" ".join(f"{b:02x}" for b in code))
