# Castle Crashers — runtime Xbox ABI imports (M2.7)

## Verified with original privately extracted XEX2 + decoded PPC PE

| Library | XEX slots | Data import descriptors | Executable thunk slots | Unique imported ordinals |
|---|---:|---:|---:|---:|
| xam.xex | 146 | 73 | 73 | 73 |
| xboxkrnl.exe | 255 | 133 | 122 | 133 |
| **Total** | **401** | **206** | **195** | **206** |

All **206 ordinals** matched public export identifiers from the Xenia
[**xam_table.inc**](https://github.com/xenia-project/xenia/blob/master/src/xenia/kernel/xam/xam_table.inc)
and [**xboxkrnl_table.inc**](https://github.com/xenia-project/xenia/blob/master/src/xenia/kernel/xboxkrnl/xboxkrnl_table.inc)
reference tables. This resolves names **at import table level**, not runtime
functions. A listed function may be unused, or only called in optional branches.

The XEX import directory contains raw guest addresses. The original PE
section table translates each address to data: **data descriptors** record the
ordinal; **executable thunk slots** refer to jump/call stubs. Distinguishing
these prevents treating 401 slots as 401 distinct APIs.

## Verified groups (examples, not a complete call trace)

- **Controllers:** XamInputGetCapabilities, XamInputGetState,
  XamInputSetState.
- **User/UI:** XamUserGetSigninState, XamUserGetName,
  XamShowSigninUI, XamNotifyCreateListener.
- **Memory:** ExAllocatePoolTypeWithTag, ExFreePool,
  NtAllocateVirtualMemory, NtFreeVirtualMemory.
- **Synchronization:** RtlEnterCriticalSection, RtlLeaveCriticalSection,
  KeWaitForSingleObject, KeInitializeSemaphore, KeReleaseSemaphore.
- **Files:** NtCreateFile, NtOpenFile, NtReadFile, NtWriteFile, NtClose.
- **GPU:** VdGetSystemCommandBuffer, VdInitializeEngines,
  VdInitializeRingBuffer, VdSwap.
- **Audio:** XAudioRegisterRenderDriverClient, XAudioSubmitRenderDriverFrame,
  XMACreateContext, XMAReleaseContext.
- **Network:** NetDll_WSAStartup, NetDll_socket, NetDll_XNetStartup.

### Priorities for reusable Xbox 360 runtime

1. First get **real ReXGlue-generated code** to compile and call a test function.
2. Implement memory, thread, locks and import ABI semantics used in early
   traces; preserve correct Xbox return/error conventions.
3. Add minimal file/resource access and local profile/controller state.
4. Progress to GPU submission, textures/shaders, audio XMA and actual game UI.
5. Validate against real runtime traces. An import list alone is **not**
   enough to assume behavior or initial call order.

## Reusable tool

```bash
python3 -m nxlab.import_contracts \
  /private/default.xex /private/castle-original-ppc.pe \
  --xam-table /sources/xenia/src/xenia/kernel/xam/xam_table.inc \
  --kernel-table /sources/xenia/src/xenia/kernel/xboxkrnl/xboxkrnl_table.inc \
  --report /private/castle-imports.json
```

The two public Xenia tables are **optional**. Without them, the tool returns
verified numeric ordinals; it never downloads game files or publishes
commercial binaries. Files derived from the real game stay in the user's
private workspace.

A successful name resolution does **not** implement that API and cannot mark
the runtime or playability gate complete.

## Remaining blockers

- ReXGlue real codegen not yet executed in the isolated development environment.
- No native PowerPC function execution, Xbox ABI implementation, GPU frame, NRO
  or Castle Crashers gameplay yet.
- Public PR includes original parser/tests only, no executable or private dump.
