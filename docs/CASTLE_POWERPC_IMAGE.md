# M2.6 — Castle Crashers original Xbox PowerPC image recovered

## Verified result (private, 19 Oct 2026)

This project has now independently recovered the original image from the
user-provided, locally authorized Castle Crashers XBLA archive.

| Item | Verified |
|---|---|
| Original XEX2 executable | 765,952 bytes |
| XEX encrypted payload | 757,760 bytes |
| AES-normal/LZX format | 14 verified SHA-1 blocks |
| Compressed LZX frame count | 90 |
| Decompressed PowerPC PE image | **2,949,120 bytes** |
| DOS/PE signatures | **MZ / PE valid** |
| PE machine | **0x01F2**, Xbox PowerPC big-endian |
| PE sections | **9**, including executable .text |
| Image base | **0x82000000** |
| Actual entry point | **0x820B7090**, matches original XEX2 header |
| LLVM disassembly of game-origin PPC | **Succeeded** |
| Code recompiled to C++ / ARM64 | **NOT YET** |
| Game executed/rendered | **NOT YET** |

The independently implemented CAB-wrapper approach reconstructed the exact
same image twice. Identical SHA-256 was measured in the private working
directory. Do **not** publish this PE, analysis ELF, individual PPC instructions
copied from the game, or any generated recompiled C++ that includes game code.

## New reusable tools

`nxlab/lzx_image.py` validates the encrypted STFS-extracted XEX, reconstructs
the LZX frames, uses **in-memory CAB** to invoke the system libarchive decoder,
validates PowerPC/Xbox PE headers and writes the recovered PE to an explicitly
private file with restrictive permissions. Any partial/invalid output is removed.

The wrapping-key file is an operator-owned, 16-byte local file under mode
0600. The repository **does not include keys** or embed a default key.

```bash
python3 -m pip install cryptography
python3 -m nxlab.lzx_image \
  /private/default.xex \
  /private/castle-original-ppc.pe \
  --wrapping-key-file /private/authorized-xex-key.bin
```

`nxlab/pe_elf.py` packages the real .text PE section into **ELF32
big-endian PowerPC** for instruction analysis (no game code embedded
in public files):

```bash
python3 -m nxlab.pe_elf /private/castle-original-ppc.pe /private/castle-text.elf
llvm-objdump -d --start-address=0x820b7090 \
  --stop-address=0x820b70e0 /private/castle-text.elf
```

The analysis ELF is not a standalone executable, a full PE loader, nor an
ARM64 binary.

### How the LZX adapter works

XEX2 normal-compression frame chunks are prefixed with big-endian chunk
lengths and chained SHA-1 blocks. **The 90 XEX chunks match the 90
decompressed 32 KiB LZX frames exactly**. A synthetic in-memory Microsoft
CAB stream places each chunk into a separate CFDATA record, with
compression type `LZX`, and lets libarchive perform the actual LZX decoding.
The original encrypted XEX stays untouched; the synthetic CAB is never
written to disk by the reusable implementation.

This works on the validated Castle Crashers sample. Other XEXs may use
different chunks/frames or other compression and must be independently
validated instead of assuming compatibility.

## Next measurable milestone: real codegen

Install a compatible [ReXGlue](https://github.com/rexglue/rexglue-sdk)
distribution with Clang 20+. Test its `init` and `codegen` commands against
the owner's private XEX and available PowerPC image. Record the exact
version, tool logs, generated function counts and blockers.

Only after actually compiling and calling one game-originated function can
the *PowerPC execution* gate be marked complete. ABI, imports, GPU, ARM64 and
real gameplay are still later steps.

No protected game assets, decrypted image, keys, or private dump are committed.
