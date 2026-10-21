#include "../../nxlab/native/goldeneye_n64_memory.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    uint8_t *dram = calloc(1, GE_N64_RDRAM_SIZE);
    static const uint8_t rom[] = {0x80, 0x37, 0x12, 0x40, 0xde, 0xad};
    assert(dram);

    ge_n64_memory memory = {0};
    void *pointer = NULL;
    uint8_t byte = 0;
    uint16_t half = 0;
    uint32_t word = 0;
    assert(ge_n64_memory_bind(&memory, dram, GE_N64_RDRAM_SIZE,
                              rom, sizeof rom) == GE_N64_MEM_OK);

    assert(ge_n64_memory_read_be32(&memory, 0x10000000, &word) == GE_N64_MEM_OK);
    assert(word == UINT32_C(0x80371240));
    assert(ge_n64_memory_resolve(&memory, 0x10000004, 2, false, &pointer)
           == GE_N64_MEM_OK);
    assert(((const uint8_t *)pointer)[0] == 0xde &&
           ((const uint8_t *)pointer)[1] == 0xad);
    assert(ge_n64_memory_write_u8(&memory, 0x10000000, 0)
           == GE_N64_MEM_READ_ONLY);
    assert(ge_n64_memory_resolve(&memory, 0x10000005, 2, false, &pointer)
           == GE_N64_MEM_BOUNDS);

    assert(ge_n64_memory_write_be32(&memory, GE_N64_K0_BASE + 0x100,
                                    UINT32_C(0x12345678)) == GE_N64_MEM_OK);
    assert(ge_n64_memory_read_be32(&memory, 0x100, &word) == GE_N64_MEM_OK);
    assert(word == UINT32_C(0x12345678));
    assert(ge_n64_memory_read_be32(&memory, GE_N64_K1_BASE + 0x100, &word)
           == GE_N64_MEM_OK && word == UINT32_C(0x12345678));
    assert(ge_n64_memory_write_be16(&memory, GE_N64_V1_BASE + 0x102,
                                    UINT16_C(0xa1b2)) == GE_N64_MEM_OK);
    assert(ge_n64_memory_read_be16(&memory, GE_N64_K0_BASE + 0x102, &half)
           == GE_N64_MEM_OK && half == UINT16_C(0xa1b2));
    assert(ge_n64_memory_read_u8(&memory, GE_N64_K0_BASE + 0x103, &byte)
           == GE_N64_MEM_OK && byte == 0xb2);

    assert(ge_n64_memory_read_be16(&memory, GE_N64_K0_BASE + 1, &half)
           == GE_N64_MEM_ALIGNMENT);
    assert(ge_n64_memory_read_be32(&memory, GE_N64_K0_BASE + 2, &word)
           == GE_N64_MEM_ALIGNMENT);
    assert(ge_n64_memory_read_be32(&memory, GE_N64_K0_BASE +
                                   GE_N64_RDRAM_SIZE, &word)
           == GE_N64_MEM_BOUNDS);
    assert(ge_n64_memory_resolve(&memory, 0xc0000000, 1, false, &pointer)
           == GE_N64_MEM_UNMAPPED);
    assert(ge_n64_memory_bind(&memory, dram, GE_N64_RDRAM_SIZE,
                              NULL, sizeof rom) == GE_N64_MEM_INVALID);

    free(dram);
    puts("d932006 N64 memory API compatibility: PASS (ROM, endian, aliases, access, bounds)");
    return 0;
}
