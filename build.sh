#!/usr/bin/env bash
# Full pipeline: build Falcon + faSM from source, assemble the hand-encoded
# boot sector with faSM, extract a flat 512-byte image, and boot it in QEMU.
#
# Requires: gcc, binutils (as/ld, 32-bit support), python3, nasm not needed,
# qemu-system-x86 (for the final boot test).
#
# Usage: ./build.sh /path/to/falcon-repo /path/to/faSM-repo
set -euo pipefail

FALCON_DIR="${1:?usage: build.sh <falcon-repo-dir> <faSM-repo-dir>}"
FASM_DIR="${2:?usage: build.sh <falcon-repo-dir> <faSM-repo-dir>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== 1. build falconc =="
( cd "$FALCON_DIR" && gcc -O2 -o falconc falconc.c )

echo "== 2. assemble the 32-bit falcon runtime =="
( cd "$FALCON_DIR" && as --32 flr.s -o flr.o )

echo "== 3. compile fasm.fl with falconc =="
cp "$FALCON_DIR/falconc" "$FASM_DIR/"
cp "$FALCON_DIR/flr.o" "$FASM_DIR/"
( cd "$FASM_DIR" && ./falconc fasm.fl -o fasm.s )

echo "== 4. assemble + link fasm =="
( cd "$FASM_DIR" && as --32 fasm.s -o fasm.o )
( cd "$FASM_DIR" && ld -m elf_i386 --allow-multiple-definition flr.o fasm.o -o fasm )

echo "== 5. hand-encode the 16-bit boot sector bytes =="
python3 "$HERE/tools/gen_bootcode.py"
mv bootcode.bin "$HERE/tools/bootcode.bin"

echo "== 6. wrap the bytes as faSM db directives =="
( cd "$HERE/tools" && python3 gen_fasm_source.py )
cp "$HERE/tools/boot.fasm" "$HERE/boot.fasm"

echo "== 7. assemble boot.fasm with faSM =="
"$FASM_DIR/fasm" "$HERE/boot.fasm" "$HERE/boot_elf"

echo "== 8. extract the flat 512-byte image (faSM's ELF has no section table," \
     "so objcopy --only-section can't be used -- dd past the fixed 84-byte" \
     "ELF+program header instead) =="
dd if="$HERE/boot_elf" of="$HERE/boot_fasm.img" bs=1 skip=84 count=512 status=none
rm -f "$HERE/boot_elf"

echo "== 9. sanity-check the image =="
[ "$(stat -c%s "$HERE/boot_fasm.img")" = "512" ] || { echo "image is not 512 bytes!"; exit 1; }
tail -c 2 "$HERE/boot_fasm.img" | od -An -t x1 | grep -q '55 aa' \
    || { echo "missing boot signature!"; exit 1; }
echo "boot_fasm.img OK (512 bytes, 55 AA signature present)"

echo "== 10. boot it in QEMU (headless, 5s) =="
timeout 5 qemu-system-i386 -drive format=raw,file="$HERE/boot_fasm.img" \
    -display none -no-reboot || true

echo "Done. Image: $HERE/boot_fasm.img"
