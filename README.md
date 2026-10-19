# lab-NX

Test-first Nintendo Switch porting laboratory. **Not** an automatic Xbox 360/PS3 game converter.

## M1 — Xbox Live Arcade STFS/XEX

A user-provided Castle Crashers XBLA package was inspected privately:
716 STFS entries, `default.xex` extracted (765,952 bytes) and its XEX2 header parsed.
No commercial files are committed.

Use Python 3.10+ on a locally extracted STFS file:

```sh
python3 -m nxlab inspect-stfs /private/584108B7.stfs --report /private/inventory.json
python3 -m nxlab extract-xex /private/584108B7.stfs /private/default.xex
python3 -m nxlab inspect-xex /private/default.xex
python3 -m unittest discover -s tests -v
```

Use a local archive tool (e.g. `7z x your_archive.7z`) to unpack an XBLA 7z before inspection. The STFS content may reside under `584108B7/000D0000/` with a long filename.

### Safety and limitations
- All processing is local and read-only with respect to the original package.
- `extract-xex` extracts **only one named, contiguous** XEX to an explicit private path.
- Fragmented STFS chains and alternate block-separation layouts have not been validated.
- XEX2 inspection reads clear metadata; encrypted/compressed executable sections are not decoded.
- No ISOs, ROMs, assets, private dumps, licenses, firmware or console keys are distributed.
- Use only software and game files you are authorized to inspect.
- Eden/devkitPro deployment, PowerPC → ARM64 recompilation and graphics compatibility remain later milestones.

See [M1 findings](docs/CASTLE_CRASHERS_M1.md). Reference documentation: [Free60 STFS](https://github.com/Free60Project/wiki/blob/master/docs/System-Software/Formats/STFS.md), [XBLA-Extract](https://github.com/ryzendew/XBLA-Extract).
