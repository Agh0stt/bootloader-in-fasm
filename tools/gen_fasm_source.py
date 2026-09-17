#!/usr/bin/env python3
"""
Wraps bootcode.bin (produced by gen_bootcode.py) as `db` directives inside a
faSM source file.

IMPORTANT: the bytes must go in `section data`, not `section text`. faSM's
instr_size() only assigns a size to IT_INSTR items when they're in the text
section -- db/times there are silently sized as zero, so raw bytes placed in
section text vanish from the output. Data-section items are sized correctly
in encode_all()'s separate data-size pass. Since our text section stays
empty, `section data` is emitted immediately after it -- i.e. starting
exactly at ELF's fixed entry point (ELF_BASE + ehdr + phdr) -- so it still
runs first when the file is loaded and the raw bytes are extracted.
"""

with open("bootcode.bin", "rb") as f:
    code = f.read()

lines = [
    "# boot.fasm -- 16-bit real-mode boot sector, hand-encoded",
    "# faSM's instr_size() only sizes IT_INSTR items in section text (db/times",
    "# are zero-sized there); raw data bytes must live in `section data`, which",
    "# is emitted immediately after (empty) .text -- so it lands exactly at the",
    "# ELF entry point (text_base + 0). objcopy/dd recovers it as a flat image.",
    "section data",
]

for i in range(0, len(code), 12):
    chunk = code[i:i + 12]
    vals = ", ".join(f"0x{b:02x}" for b in chunk)
    lines.append(f"    db {vals}")

pad = 510 - len(code)
assert pad >= 0, "boot code plus BIOS signature must fit in 512 bytes"
lines.append(f"    times {pad} db 0")
lines.append("    db 0x55, 0xaa   # BIOS boot signature")

with open("boot.fasm", "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"wrote boot.fasm ({len(code)} code bytes + {pad} padding + 2 signature bytes)")
