#include "goldeneye_n64_memory.h"
#include <string.h>

static int valid(const ge_n64_memory *m)
{
    return m && m->bytes && m->size > 0 && m->size <= UINT32_C(0x02000000);
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
    if (address < UINT32_C(0x02000000)) {
        offset = address;
    } else if (address >= GE_N64_V1_BASE &&
               address < GE_N64_V1_BASE + UINT32_C(0x02000000)) {
        offset = address - GE_N64_V1_BASE;
    } else if ((address & UINT32_C(0xE0000000)) == GE_N64_K0_BASE ||
               (address & UINT32_C(0xE0000000)) == GE_N64_K1_BASE) {
        offset = address & UINT32_C(0x1FFFFFFF);
    } else {
        return GE_N64_ADDRESS;
    }
    if (offset > m->size || length > m->size - offset) return GE_N64_RANGE;
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

static ge_n64_mem_result legacy_result(ge_n64_result result)
{
    switch (result) {
    case GE_N64_OK: return GE_N64_MEM_OK;
    case GE_N64_ARGUMENT: return GE_N64_MEM_INVALID;
    case GE_N64_RANGE: return GE_N64_MEM_BOUNDS;
    case GE_N64_ADDRESS:
    case GE_N64_SEGMENT_UNBOUND: return GE_N64_MEM_UNMAPPED;
    }
    return GE_N64_MEM_INVALID;
}

ge_n64_mem_result ge_n64_memory_bind(ge_n64_memory *m, uint8_t *dram,
    size_t dram_size, const uint8_t *rom, size_t rom_size)
{
    if (!m || !dram || !dram_size || dram_size > UINT32_C(0x02000000) ||
        !rom || !rom_size || rom_size > UINT32_C(0x10000000))
        return GE_N64_MEM_INVALID;
    memset(m, 0, sizeof *m);
    m->bytes = dram;
    m->size = dram_size;
    m->rom = rom;
    m->rom_size = rom_size;
    return GE_N64_MEM_OK;
}

ge_n64_mem_result ge_n64_memory_resolve(const ge_n64_memory *m,
    uint32_t address, size_t length, bool write_access, void **host_pointer)
{
    if (!valid(m) || !m->rom || !m->rom_size || !host_pointer)
        return GE_N64_MEM_INVALID;
    *host_pointer = NULL;
    if (address >= UINT32_C(0x10000000) && address < UINT32_C(0x20000000)) {
        size_t offset = (size_t)(address - UINT32_C(0x10000000));
        if (offset > m->rom_size || length > m->rom_size - offset)
            return GE_N64_MEM_BOUNDS;
        if (write_access) return GE_N64_MEM_READ_ONLY;
        *host_pointer = (void *)(uintptr_t)(m->rom + offset);
        return GE_N64_MEM_OK;
    }
    return legacy_result(ge_n64_memory_span(m, address, length, host_pointer));
}

static ge_n64_mem_result legacy_read(const ge_n64_memory *m, uint32_t address,
    size_t length, size_t alignment, uint32_t *value)
{
    if (!value) return GE_N64_MEM_INVALID;
    if (alignment > 1 && address % alignment) return GE_N64_MEM_ALIGNMENT;
    void *pointer;
    ge_n64_mem_result result = ge_n64_memory_resolve(m, address, length, false,
                                                      &pointer);
    if (result != GE_N64_MEM_OK) return result;
    const uint8_t *bytes = pointer;
    uint32_t decoded = bytes[0];
    for (size_t i = 1; i < length; ++i) decoded = (decoded << 8) | bytes[i];
    *value = decoded;
    return GE_N64_MEM_OK;
}

static ge_n64_mem_result legacy_write(const ge_n64_memory *m, uint32_t address,
    size_t length, size_t alignment, uint32_t value)
{
    if (alignment > 1 && address % alignment) return GE_N64_MEM_ALIGNMENT;
    void *pointer;
    ge_n64_mem_result result = ge_n64_memory_resolve(m, address, length, true,
                                                      &pointer);
    if (result != GE_N64_MEM_OK) return result;
    uint8_t *bytes = pointer;
    for (size_t i = 0; i < length; ++i) {
        bytes[length - 1 - i] = (uint8_t)value;
        value >>= 8;
    }
    return GE_N64_MEM_OK;
}

ge_n64_mem_result ge_n64_memory_read_u8(const ge_n64_memory *m,
    uint32_t address, uint8_t *value)
{
    uint32_t decoded;
    ge_n64_mem_result result = legacy_read(m, address, 1, 1, &decoded);
    if (result == GE_N64_MEM_OK && value) *value = (uint8_t)decoded;
    else if (!value) return GE_N64_MEM_INVALID;
    return result;
}

ge_n64_mem_result ge_n64_memory_read_be16(const ge_n64_memory *m,
    uint32_t address, uint16_t *value)
{
    uint32_t decoded;
    ge_n64_mem_result result = legacy_read(m, address, 2, 2, &decoded);
    if (result == GE_N64_MEM_OK && value) *value = (uint16_t)decoded;
    else if (!value) return GE_N64_MEM_INVALID;
    return result;
}

ge_n64_mem_result ge_n64_memory_read_be32(const ge_n64_memory *m,
    uint32_t address, uint32_t *value)
{
    return legacy_read(m, address, 4, 4, value);
}

ge_n64_mem_result ge_n64_memory_write_u8(const ge_n64_memory *m,
    uint32_t address, uint8_t value)
{
    return legacy_write(m, address, 1, 1, value);
}

ge_n64_mem_result ge_n64_memory_write_be16(const ge_n64_memory *m,
    uint32_t address, uint16_t value)
{
    return legacy_write(m, address, 2, 2, value);
}

ge_n64_mem_result ge_n64_memory_write_be32(const ge_n64_memory *m,
    uint32_t address, uint32_t value)
{
    return legacy_write(m, address, 4, 4, value);
}
