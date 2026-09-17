# bootloader-fasm

A minimal BIOS boot sector, assembled with **fasm** — a 32-bit x86 assembler written in
**Falcon** (https://github.com/Agh0stt/falcon) — instead of nasm.

It prints:

    Hello from a working bootloader!

directly from BIOS real mode, verified booting in QEMU (screenshot below).

## Why this isn't a normal faSM job

faSM targets 32-bit protected mode and always emits a fixed-format ELF32
executable. A classic BIOS boot sector needs:

- 16-bit real-mode code (faSM only has 32-bit registers: `%eax`, `%ecx`, ...
  — no `%ax`, `%si`, `%ds`, `%es`, `%ss`, `%sp`)
- no `BITS 16` / `ORG 0x7C00` directives (faSM has neither)
- a flat 512-byte binary ending in the `0x55 0xAA` signature, not an ELF

So faSM can't assemble the boot sector's *instructions* directly. What it
*can* do is emit raw bytes verbatim via `db`. The approach here:

1. **`tools/gen_bootcode.py`** hand-encodes the boot sector's 16-bit x86
   machine code, byte by byte (registers, memory addresses, and jump
   displacements all resolved manually) — the same thing a real 16-bit
   assembler would do internally.
2. **`tools/gen_fasm_source.py`** wraps those bytes as `db 0x.., 0x.., ...`
   lines in `boot.fasm`, to be assembled *by faSM itself*.
3. One faSM-specific catch surfaced here: faSM's `instr_size()` only assigns
   a nonzero size to real instructions (`IT_INSTR`) inside `section text` —
   `db`/`times` placed there are silently sized as **zero** and vanish from
   the output. Data-section items go through a separate, correctly-sized
   pass. Fix: put the bytes in `section data` instead. Since `section text`
   stays empty, `section data` is emitted immediately after it — i.e.
   starting exactly at faSM's fixed ELF entry point — so the bytes still end
   up first when the file is loaded.
4. faSM's ELF output has **no section header table** (by design — see its
   own README), so `objcopy --only-section=.text` doesn't work on it. The
   flat image is instead recovered with `dd`, skipping the fixed 84-byte
   ELF header + program header (`52 + 32`) that precede the data in every
   faSM-produced executable.
5. The result is byte-for-byte the same as what `tools/gen_bootcode.py`
   produced, plus zero padding and the `55 AA` signature — but it went
   *through faSM* to get there.

## Files

    boot.fasm          faSM source: the boot sector as db-byte directives
    boot_fasm.img       the assembled, extracted 512-byte flat boot image
    screendump.png       QEMU screenshot proving it boots and prints
    tools/gen_bootcode.py     hand-encodes the 16-bit machine code
    tools/gen_fasm_source.py  wraps those bytes as a faSM source file
    build.sh                  full pipeline, start to finish

## Building

Requires the `falcon` and `faSM` repos (clone alongside this one), plus
`gcc`, `binutils` (`as`/`ld` with 32-bit support), `python3`, and
`qemu-system-x86` for the final boot test.

    git clone https://github.com/Agh0stt/falcon.git
    git clone https://github.com/Agh0stt/faSM.git
    ./build.sh ./falcon ./faSM

This builds `falconc`, compiles `fasm.fl` through it to produce a working
`fasm` binary, assembles `boot.fasm` with that binary, extracts
`boot_fasm.img`, and boots it in QEMU headless as a sanity check.

## Running it yourself

    qemu-system-i386 -drive format=raw,file=boot_fasm.img

or write it to a USB drive / disk image and boot real hardware:

    sudo dd if=boot_fasm.img of=/dev/sdX bs=512 count=1

## Boot sector logic

Sets up segment registers and the stack, then loops over a null-terminated
string calling BIOS teletype output (`int 0x10, ah=0x0E`) for each byte,
and halts (`cli; hlt`) when done.
