# Castle Crashers: direct 7z/ZIP-to-XEX pipeline

This change removes a previously manual step. The XEX and game assets stay **private**.

## Run on Linux Mint (with libarchive installed)

```bash
python3 -m nxlab.auto \
  --input "/private/Castle Crashers (World) (XBLA) (1).7z" \
  --workspace "$HOME/labnx-private" \
  --project castle_crashers
```

Or use the goal supervisor:

```bash
python3 -m nxlab.goal_manager \
  --input "/private/Castle Crashers (World) (XBLA) (1).7z" \
  --workspace "$HOME/labnx-private" \
  --recipe castle-crashers --codegen --bonsai
```

The input is selected by magic, not its filename. It may be a raw STFS
(LIVE/PIRS/CON), XEX2, 7z, or ZIP. libarchive is a system library accessed
directly through Python ctypes (no `7z` CLI and no Python pip dependency).
The archive must contain **exactly one** regular STFS payload. The game
archive is neither changed nor extracted into the Git checkout.

## Validated with the private original game dump

- Original 7z: **112,125,567 bytes**.
- libarchive saw **5 entries** (three directories, one STFS payload, one text file).
- The STFS contained **146,616,320 bytes** and was extracted in ~4.55 seconds
  under the provided test environment.
- SHA-256 exactly matched the independently extracted private STFS from the
  preceding M1 sessions (hash itself retained in private evidence).
- STFS parser recognized **716 entries**, **708 files**, **8 directories**.
- `default.xex`: **765,952 bytes**, correct contiguous STFS region.
- The previous M2 metadata reader already verified encrypted/LZX metadata,
  entry point, and import descriptors; **no PPC image was decrypted or executed**.

## Boundaries and security

- 2 GiB maximum compressed archive, 1 GiB maximum STFS member,
  100,000 entries; input is read-only.
- No archive-provided path is used for writing to disk. A private, fixed
  destination is used; path traversal and symlink entries cannot create files.
- Multiple STFS-like payloads are considered ambiguous and the extraction is
  removed. Existing outputs are never overwritten.
- No commercial file, XEX, key, shader, ROM, archive or media is committed.
- Unit and synthetic end-to-end ZIP-to-XEX tests run in CI when libarchive is
  present; actual 7z testing uses the user's private game outside Git.
- libarchive is not a sandbox for malicious archives; only inspect trusted,
  authorized files in a restricted user environment.
- An archive parsing success does **not** imply ReXGlue codegen, native PPC
  execution, graphics output, menu, or Switch gameplay.

## Next engineering obstacle

This specific `default.xex` reports normal encryption and LZX compression.
A current, executable ReXGlue distribution, its compatible host toolchain and
access to an authorized image are still required. On the isolated container
used for validation, ReXGlue, Clang 20+, devkitPro and Eden are not installed;
attempts to reach external GitHub hosts failed due to DNS/network restrictions.

The new 7z importer directly improves source preparation for Castle Crashers,
Forza/Fallout packages in supported formats and future XBLA projects. ISO/XDVDFS
handling is **not** implemented by this change.
