#include "goldeneye_n64_memory.h"
#include <string.h>

static int valid(const ge_n64_memory *m)
{
    return m && m->bytes && m->size == GE_N64_RDRAM_SIZE;
}

ge_n64_result ge_n64_memory_init(ge_n64_memory *m, void *backing, size_t size)
{
    if (!m || !backing || size != GE_N64_RDRAM_SIZE)
        return GE_N64_ARGUMENT;
    memset(m, 0, sizeof *m);
    m->bytes = backing;
    m->size = size;
    return GE_N64_OK;
}

ge_n64_result ge_n64_memory_span(const ge_n64_memory *m, uint32_t address,
                               size_t length, void **out)
{
    if (!valid(m) || !out || !length) return GE_N64_ARGUMENT;
    uint32_t offset;
    if (address < GE_N64_RDRAM_SIZE) offset = address;
    else if (address >= GE_N64_V1_BASE && address - GE_N64_V1_BASE < m->size)
        offset = address - GE_N64_V1_BASE;
    else if (address >= GE_N64_K0_BASE && address - GE_N64_K0_BASE < m->size)
        offset = address - GE_N64_K0_BASE;
    else if (address >= GE_N64_K1_BASE && address - GE_N64_K1_BASE < m->size)
        offset = address - GE_N64_K1_BASE;
    else return GE_N64_ADDRESS;
    if (length > m->size - offset) return GE_N64_RANGE;
    *out = m->bytes + offset;
    return GE_N64_OK;
}

ge_n64_result ge_n64_memory_physical(const ge_n64_memory *m,
                                   const void *host, size_t length, uint32_t *out)
{
    if (!valid(m) || !host || !out || !length) return GE_N64_ARGUMENT;
    uintptr_t start = (uintptr_t)m->bytes, addr = (uintptr_t)host;
    if (addr < start || addr - start >= m->size) return GE_N64_ADDRESS;
    size_t offset = addr - start;
    if (length > m->size - offset) return GE_N64_RANGE;
    *out = (uint32_t)offset;
    return GE_N64_OK;
}

ge_n64_result ge_n64_memory_bind_segment(ge_n64_memory *m, unsigned segment,
                                       void *backing, size_t size)
{
    if (!valid(m) || !segment || segment >= 16 || (!!backing != !!size))
        return GE_N64_ARGUMENT;
    m->segments[segment].bytes = backing;
    m->segments[segment].size = size;
    return GE_N64_OK;
}

ge_n64_result ge_n64_memory_display_span(const ge_n64_memory *m,
                                       uint32_t word, size_t length, void **out)
{
    if (!valid(m) || !out || !length) return GE_N64_ARGUMENT;
    unsigned segment = (word >> 24) & 15u;
    if (word < 0x10000000u && segment) {
        if (!m->segments[segment].bytes) return GE_N64_SEGMENT_UNBOUND;
        /* Segment 5's special unmarked path precedes the tagged path in
         * upstream gfx_pc.cpp, so even an odd offset stays odd there. */
        uint32_t offset = word & 0x00ffffffu;
        if (segment != 5 && (word & 1u)) offset &= ~1u;
        if (offset >= m->segments[segment].size ||
            length > m->segments[segment].size - offset) return GE_N64_RANGE;
        *out = m->segments[segment].bytes + offset;
        return GE_N64_OK;
    }
    return ge_n64_memory_span(m, word, length, out);
}
