# Castle Crashers — M1 evidence (metadata only)

- Source: user's private Google Drive `Ports` folder. The game archive is **not** included.
- Container: Xbox 360 STFS `LIVE`; content type `000D0000`; title ID `584108B7`.
- Uncompressed container: **146,616,320 bytes**.
- Entries: **716** (708 files, 8 directories).
- Game assets: 198 `.pak`, 26 `.png`, 464 `.xma`, 15 `.xpu`, 2 `.xvu`, 1 `.xpr`, 1 `.xml`.
- Executable: `default.xex`, **765,952 bytes**, STFS block **123**, contiguous, **187** blocks.
- Executable signature: **XEX2**; `pe_data_offset=8192`, `security_info_offset=144`, **15 optional headers**.
- Extracted privately and read-only, with expected byte count and valid magic.
- Local 14-test suite for NX-Lab v0.2.1 + M1 parser: **14 passed**. Remote compact M1 implementation requires CI confirmation.
- **Not yet demonstrated:** PowerPC code decryption, recompilation, Xbox runtime, gameplay, Eden/Switch execution.

This report intentionally contains no commercial game bytes, assets, keys or executable.
