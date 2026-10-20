#!/usr/bin/env python3
"""Verify original and compatibility dekomme headers write identical GPU RAM.

Also checks each exported macro starts its own suffix upload, avoiding Eden's
mid-macro materialization. No ROM or proprietary instructions are involved.
"""
import argparse
import re
from pathlib import Path


def decode(path):
    source = Path(path).read_text()
    words = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]+),", source.split("#endif", 1)[1])]
    ram, starts, bindings = {}, {}, {}
    instruction = binding = None
    index = 0
    while index < len(words):
        header = words[index]
        index += 1
        mode, count, subchannel, method = header >> 29, (header >> 16) & 0x1FFF, (header >> 13) & 7, header & 0x1FFF
        assert mode == 5 and subchannel == 0, (mode, subchannel)
        assert count > 1 and index + count <= len(words)
        data = words[index:index + count]
        index += count
        if method == 0x45:
            instruction = data[0]
            starts[instruction] = data[1:]
            for word in data[1:]:
                if instruction in ram:
                    assert ram[instruction] == word, "overlapping uploads changed instruction bytes"
                ram[instruction] = word
                instruction += 1
        elif method == 0x47:
            binding = data[0]
            for word in data[1:]:
                bindings[binding] = word
                binding += 1
        else:
            raise AssertionError(f"unexpected method {method:x}")
    assert ram and bindings
    return ram, starts, bindings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original")
    parser.add_argument("compat")
    args = parser.parse_args()
    original, _, original_bindings = decode(args.original)
    compat, starts, bindings = decode(args.compat)
    assert original == compat, "GPU instruction RAM changed"
    assert original_bindings == bindings, "GPU macro bindings changed"
    for start in bindings.values():
        assert start in starts, f"export {start} still requires mid-macro extraction"
        assert starts[start] == [original[i] for i in range(start, len(original))]
    print(f"MME upload equivalence: PASS ({len(original)} instructions, {len(bindings)} exports)")


if __name__ == "__main__":
    main()
