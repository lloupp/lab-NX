# M2.8 — Native execution of small, real PowerPC code snippets

## Proven locally against user's original Castle Crashers PowerPC PE

The decoded, original Xbox 360 PowerPC PE remained in a private workspace.
A generic, **limited** PowerPC -> C++ translator consumed sequences from its
real executable `.text` section, generated C++ privately, compiled that code
with the host C++ compiler and executed five independent input vectors for
each sequence.

| Game address | Instructions | Native execution | Examples |
|---|---|---|---|
| 0x8205A08C | addi / blr | 5/5 matched | Returns 23 |
| 0x820E4520 | addis / ori / blr | 5/5 matched | Returns 0x80004005 |
| 0x8208EE10 | addi / blr | 5/5 matched | Input-dependent pointer offset, result = input + 104 (mod 2^32) |

**Total real-game checks: 15 / 15**. The third snippet tests input-dependent
behavior including 32-bit wraparound, not only constant returns. The code
was translated from game-origin bytes; the generated derivative C++ and
native binaries were kept private and **not committed**.

This is a **narrow native execution proof**, not a ReXGlue success or proof
that full functions with the Xbox ABI have been recompiled. Function boundaries,
callers, runtime behavior and correctness against an actual Xbox runtime
have not been independently verified. The interpreter is an implementation
of the same small instruction subset and is not an Xbox hardware oracle.

## Reproducible private command

```bash
python3 -m nxlab.ppc_leaf /private/castle-original-ppc.pe \
  --address 0x8208EE10 --instructions 2 \
  --workspace /private/labnx-leaf-trial1
```

Outputs inside the private run directory:

- `guest_lift.cpp`: generated **game-derived** source, never publish.
- `guest_lift`: compiled executable for local x86-64/Linux host.
- `evidence.json`: input/output comparison and hashes only.

The translator supports only `addi`, `addis`, `ori`, `xori`, and a
terminal `blr` (short snippets up to 64 instructions). Unsupported
branches, memory accesses, calls, and VMX operations fail closed; it does not
claim broad PowerPC compatibility.

## Validation

Six tests with a **synthetic PE** cover integer operations, wraparound,
unsupported instructions, section bounds, native build and run.
`python3 -m unittest discover -s tests -v` runs this suite in the larger
NX-Lab project.

## Remaining milestones

- Install and invoke a **real ReXGlue SDK** on the private Xbox XEX; compare
  function discovery and generated C++ with this bounded experiment.
- Determine genuine function boundaries and independently validate full
  call behavior and ABI/calling conventions.
- Implement Xbox runtime services (206 Castle Crashers import ordinals
  identified but not yet implemented) and GPU/audio support.
- Compile a real NRO and reach authentic menu/gameplay in Eden/Switch.

No commercial game files, PowerPC bytes, keys or generated derivative game
code are included in the public repository. **Castle Crashers is not playable.**
