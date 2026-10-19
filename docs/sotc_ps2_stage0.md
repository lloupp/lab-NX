# Shadow of the Colossus (USA PS2) — stage 0

Local inventory validated on 2026-10-19 after reconstructing the user-provided seven-part archive. The outer 7z contained the original 7z, and the original archive contained an ISO image.

## Private ISO findings

| Item | Verification |
|---|---|
| ISO size | 2,693,955,584 bytes |
| ISO SHA-256 | `d431a5b7e6c7009713d743c22ac5fd61077da40d5f7923e3250fe072a226eacb` |
| Filesystem | ISO 9660, primary volume descriptor valid |
| SYSTEM.CNF | `BOOT2 = cdrom0:\\SCUS_974.72;1` |
| Boot ELF | 32-bit little-endian MIPS, entry `0x00100010` |
| Boot ELF size | 242,940 bytes |
| Boot ELF SHA-256 | `d16ad76ba8cdf87695d94b1316d51c1f248959ec0749814c31bb7a2d55d9a2e1` |
| KERNEL.XFF | 415,908 bytes |
| MANAGER.XFF | 1,650,876 bytes |
| GAMECORE.XFF | 2,141,864 bytes |
| NICO.DAT | 2,667,340,678 bytes |

No game data, copyrighted binaries, or game scenes are stored in the public repo. This stage proves archive integrity and PS2 executable identification, **not** Switch gameplay.

## Re-run locally

```bash
python3 -m unittest discover -s tests -v
python3 tools/ps2_iso_inventory.py "/private/path/Shadow of the Colossus (USA).iso" --hash-iso --json
```

The inspector emits file names, sizes and hashes, not game content.

## Port direction

1. Review upstream [Celosia](https://github.com/HenryKun55/celosia), GPL-3.0. It targets the **same SCUS-97472 US retail release** and reports static MIPS-to-C++ recompilation with [PS2Recomp](https://github.com/ran-j/PS2Recomp), working macOS gameplay and an experimental PS Vita ARM port. Those are upstream claims, not results from lab-NX or evidence of Switch execution.
2. Independently match binary hashes/module structure to upstream expected revisions. Keep original input files private and outside CI.
3. Reproduce upstream supported-platform boot and game images before porting.
4. Isolate target-specific filesystem, memory, audio, input, timing, threads and graphics; adapt Vita-side common code to Switch libnx/ARM64 with a suitable deko3d renderer.
5. Validate in order: compiled NRO, Eden runtime, real original frames, real controller input, sustained gameplay, physical Switch V2 performance.

References:
- [Celosia — native macOS / Vita recompilation](https://github.com/HenryKun55/celosia)
- [TheRealestNwah/sotc-decomp — matching US PS2 decompilation](https://github.com/TheRealestNwah/sotc-decomp)
- [Fantaskink/SOTC — different Japanese preview target, not binary-equivalent](https://github.com/Fantaskink/SOTC)

If Celosia code is incorporated, retain GPL-3.0 license notices. No scenes or benchmarks on Nintendo Switch are claimed at this stage.
