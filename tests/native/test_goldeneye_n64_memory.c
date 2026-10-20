#include "goldeneye_n64_memory.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    uint8_t *ram = calloc(1, GE_N64_RDRAM_SIZE);
    assert(ram);
    ge_n64_memory m;
    assert(ge_n64_memory_init(&m, ram, GE_N64_RDRAM_SIZE) == GE_N64_OK);
    assert(ge_n64_memory_init(&m, ram, 1) == GE_N64_ARGUMENT);
    const uint32_t bases[] = {0, GE_N64_V1_BASE, GE_N64_K0_BASE, GE_N64_K1_BASE};
    ram[0x50000] = 0x5a;
    for (unsigned i = 0; i < 4; ++i) {
        void *p = NULL;
        assert(ge_n64_memory_span(&m, bases[i] + 0x50000, 1, &p) == GE_N64_OK);
        assert(p == ram + 0x50000 && *(uint8_t *)p == 0x5a);
        assert(ge_n64_memory_span(&m, bases[i] + GE_N64_RDRAM_SIZE - 1, 1, &p) == GE_N64_OK);
        assert(p == ram + GE_N64_RDRAM_SIZE - 1);
        assert(ge_n64_memory_span(&m, bases[i] + GE_N64_RDRAM_SIZE - 1, 2, &p) == GE_N64_RANGE);
    }
    void *p = ram;
    assert(ge_n64_memory_span(&m, 0xffffffffu, SIZE_MAX, &p) == GE_N64_ADDRESS);
    assert(ge_n64_memory_span(&m, 0, SIZE_MAX, &p) == GE_N64_RANGE);
    assert(ge_n64_memory_span(&m, 0, 0, &p) == GE_N64_ARGUMENT);
    assert(p == ram);
    uint32_t phys = 999;
    assert(ge_n64_memory_physical(&m, ram + 0x50000, 64, &phys) == GE_N64_OK);
    assert(phys == 0x50000);
    assert(ge_n64_memory_physical(&m, ram + GE_N64_RDRAM_SIZE, 1, &phys) == GE_N64_ADDRESS);
    assert(phys == 0x50000);
    uint8_t vertices[64] = {0};
    assert(ge_n64_memory_bind_segment(&m, 0, vertices, 64) == GE_N64_ARGUMENT);
    assert(ge_n64_memory_bind_segment(&m, 16, vertices, 64) == GE_N64_ARGUMENT);
    assert(ge_n64_memory_display_span(&m, 0x04000001, 16, &p) == GE_N64_SEGMENT_UNBOUND);
    assert(ge_n64_memory_bind_segment(&m, 4, vertices, 64) == GE_N64_OK);
    assert(ge_n64_memory_display_span(&m, 0x04000011, 16, &p) == GE_N64_OK);
    assert(p == vertices + 16);
    assert(ge_n64_memory_display_span(&m, 0x04000010, 16, &p) == GE_N64_OK);
    assert(p == vertices + 16);
    assert(ge_n64_memory_display_span(&m, 0x0400003e, 3, &p) == GE_N64_RANGE);
    assert(ge_n64_memory_bind_segment(&m, 5, vertices, 64) == GE_N64_OK);
    assert(ge_n64_memory_display_span(&m, 0x05000011, 16, &p) == GE_N64_OK);
    assert(p == vertices + 17);
    assert(ge_n64_memory_bind_segment(&m, 4, NULL, 0) == GE_N64_OK);
    assert(ge_n64_memory_display_span(&m, 0x04000010, 1, &p) == GE_N64_SEGMENT_UNBOUND);
    assert(ge_n64_memory_display_span(&m, GE_N64_K0_BASE + 32, 32, &p) == GE_N64_OK);
    assert(p == ram + 32);
    free(ram);
    puts("N64 address translation and bounded Fast3D segments: PASS (no engine execution)");
    return 0;
}
